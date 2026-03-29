"""Tests for Argo CD cookie refresh logic."""

import httpx

from mcp_read_only_argocd.argocd_connector import ArgoCDConnector
from mcp_read_only_argocd.config import ArgoCDConnection


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


def test_direct_connection_reload_uses_runtime_environment(monkeypatch):
    monkeypatch.setenv("ARGOCD_SESSION_TEST", "runtime-session")

    conn = ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
    )

    assert conn.reload_session_token() == "runtime-session"
