"""Tests for Argo CD cookie refresh logic."""

import httpx
import pytest
import yaml

from mcp_read_only_argocd.argocd_connector import ArgoCDConnector
from mcp_read_only_argocd.config import ArgoCDConnection
from mcp_read_only_argocd.config import ConfigParser
from mcp_read_only_argocd.exceptions import AuthenticationError, PermissionDeniedError


def test_parse_set_cookie_header_updates_token():
    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="old_token_123",
    )
    connector = ArgoCDConnector(conn)

    mock_response = httpx.Response(
        status_code=200,
        headers={
            "set-cookie": "argocd.token=new_token_456; Path=/; HttpOnly; SameSite=Lax"
        },
        content=b'{"status": "ok"}',
    )

    connector._check_and_update_session_cookie(mock_response)

    assert connector.connection.session_token == "new_token_456"


def test_parse_url_encoded_cookie_value():
    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="old_token",
    )
    connector = ArgoCDConnector(conn)

    mock_response = httpx.Response(
        status_code=200,
        headers={"set-cookie": "argocd.token=abc%2B123%3Dtest; Path=/"},
        content=b'{"status": "ok"}',
    )

    connector._check_and_update_session_cookie(mock_response)

    assert connector.connection.session_token == "abc+123=test"


def test_no_set_cookie_header_leaves_token_unchanged():
    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="original_token",
    )
    connector = ArgoCDConnector(conn)

    mock_response = httpx.Response(
        status_code=200, headers={}, content=b'{"status": "ok"}'
    )

    connector._check_and_update_session_cookie(mock_response)

    assert connector.connection.session_token == "original_token"


def test_same_token_not_updated():
    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="same_token_123",
    )
    connector = ArgoCDConnector(conn)

    mock_response = httpx.Response(
        status_code=200,
        headers={"set-cookie": "argocd.token=same_token_123; Path=/"},
        content=b'{"status": "ok"}',
    )

    connector._check_and_update_session_cookie(mock_response)

    assert connector.connection.session_token == "same_token_123"


def test_multiple_set_cookie_headers_only_argocd_token_used():
    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="old_token",
    )
    connector = ArgoCDConnector(conn)

    mock_response = httpx.Response(
        status_code=200,
        headers=httpx.Headers(
            [
                ("set-cookie", "other_cookie=value1; Path=/"),
                ("set-cookie", "argocd.token=new_token_789; Path=/"),
                ("set-cookie", "argocd.token_expiry=1234567890; Path=/"),
            ]
        ),
        content=b'{"status": "ok"}',
    )

    connector._check_and_update_session_cookie(mock_response)

    assert connector.connection.session_token == "new_token_789"


def test_direct_connection_reload_uses_configured_session_token():
    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="configured-session",
    )

    assert conn.reload_session_token() == "configured-session"


@pytest.mark.asyncio
async def test_401_refreshes_from_chrome_retries_and_persists_yaml(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "connections.yaml"
    config_path.write_text(
        "- connection_name: test\n"
        "  url: https://argocd.example.com\n"
        "  session_token: stale-token\n",
        encoding="utf-8",
    )
    [conn] = ConfigParser(config_path).load_config()
    connector = ArgoCDConnector(conn)
    cookies_seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        cookies_seen.append(request.headers.get("cookie", ""))
        if len(cookies_seen) == 1:
            return httpx.Response(401, request=request)

        return httpx.Response(200, json={"items": []}, request=request)

    connector.client = httpx.AsyncClient(
        base_url=str(conn.url),
        cookies={"argocd.token": conn.session_token or ""},
        timeout=conn.timeout,
        verify=conn.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(
        "mcp_read_only_argocd.argocd_connector.load_session_token_from_chrome",
        lambda url: "fresh-token",
    )

    result = await connector.list_applications()
    await connector.close()

    assert result == []
    assert cookies_seen == [
        "argocd.token=stale-token",
        "argocd.token=fresh-token",
    ]
    assert conn.session_token == "fresh-token"
    saved_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved_config[0]["session_token"] == "fresh-token"


@pytest.mark.asyncio
async def test_401_does_not_persist_chrome_token_when_retry_fails(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "connections.yaml"
    config_path.write_text(
        "- connection_name: test\n"
        "  url: https://argocd.example.com\n"
        "  session_token: stale-token\n",
        encoding="utf-8",
    )
    [conn] = ConfigParser(config_path).load_config()
    connector = ArgoCDConnector(conn)
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(401, request=request)

    connector.client = httpx.AsyncClient(
        base_url=str(conn.url),
        cookies={"argocd.token": conn.session_token or ""},
        timeout=conn.timeout,
        verify=conn.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(
        "mcp_read_only_argocd.argocd_connector.load_session_token_from_chrome",
        lambda url: "fresh-token",
    )

    with pytest.raises(AuthenticationError):
        await connector.list_applications()

    await connector.close()
    saved_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert request_count == 2
    assert saved_config[0]["session_token"] == "stale-token"


@pytest.mark.asyncio
async def test_401_persists_chrome_token_when_retry_authenticates_but_is_forbidden(
    tmp_path, monkeypatch
):
    config_path = tmp_path / "connections.yaml"
    config_path.write_text(
        "- connection_name: test\n"
        "  url: https://argocd.example.com\n"
        "  session_token: stale-token\n",
        encoding="utf-8",
    )
    [conn] = ConfigParser(config_path).load_config()
    connector = ArgoCDConnector(conn)

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("cookie") == "argocd.token=stale-token":
            return httpx.Response(401, request=request)
        return httpx.Response(403, request=request)

    connector.client = httpx.AsyncClient(
        base_url=str(conn.url),
        cookies={"argocd.token": conn.session_token or ""},
        timeout=conn.timeout,
        verify=conn.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(
        "mcp_read_only_argocd.argocd_connector.load_session_token_from_chrome",
        lambda url: "fresh-token",
    )

    with pytest.raises(PermissionDeniedError):
        await connector.list_applications()

    await connector.close()
    saved_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved_config[0]["session_token"] == "fresh-token"


@pytest.mark.asyncio
async def test_401_raises_when_chrome_has_no_new_token(monkeypatch):
    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="stale-token",
    )
    connector = ArgoCDConnector(conn)
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(401, request=request)

    connector.client = httpx.AsyncClient(
        base_url=str(conn.url),
        cookies={"argocd.token": conn.session_token or ""},
        timeout=conn.timeout,
        verify=conn.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(
        "mcp_read_only_argocd.argocd_connector.load_session_token_from_chrome",
        lambda url: None,
    )

    with pytest.raises(AuthenticationError) as excinfo:
        await connector.list_applications()

    await connector.close()
    assert request_count == 1
    assert "no matching argocd.token was found in Chrome Profile 1" in str(
        excinfo.value
    )
