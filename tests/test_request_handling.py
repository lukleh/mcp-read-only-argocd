"""Tests for request handling edge cases in ArgoCDConnector."""

import httpx
import pytest

from src.argocd_connector import ArgoCDConnector
from src.config import ArgoCDConnection
from src.exceptions import ArgoCDAPIError


def create_mock_connector(connection, handler):
    """Create a connector with a mock transport."""
    connector = ArgoCDConnector(connection)
    connector.client = httpx.AsyncClient(
        base_url=str(connection.url),
        cookies={"argocd.token": connection.session_token or ""},
        timeout=connection.timeout,
        verify=connection.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    return connector


@pytest.fixture
def connection(monkeypatch):
    monkeypatch.setenv("ARGOCD_SESSION_TEST", "test_session_token")
    return ArgoCDConnection(
        connection_name="test",
        url="https://argocd.example.com",
        session_token="test_session_token",
    )


@pytest.mark.asyncio
async def test_get_application_quotes_name(connection):
    """Application names should be encoded before they enter the URL path."""
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.raw_path.decode()
        return httpx.Response(200, json={"metadata": {"name": "demo"}})

    connector = create_mock_connector(connection, handler)
    result = await connector.get_application("team/app?#demo")
    await connector.client.aclose()

    assert result["metadata"]["name"] == "demo"
    assert captured["path"].endswith("/applications/team%2Fapp%3F%23demo")


@pytest.mark.asyncio
async def test_get_application_logs_preserves_zero_values(connection):
    """Explicit zero values should survive query-parameter construction."""
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = str(request.url)
        return httpx.Response(200, json={"items": []})

    connector = create_mock_connector(connection, handler)
    await connector.get_application_logs("demo", tail_lines=0, since_seconds=0)
    await connector.client.aclose()

    assert "tailLines=0" in captured["query"]
    assert "sinceSeconds=0" in captured["query"]


@pytest.mark.asyncio
async def test_get_wraps_request_errors(connection):
    """Transport failures should be normalized into ArgoCDAPIError."""

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    connector = create_mock_connector(connection, handler)

    with pytest.raises(ArgoCDAPIError) as excinfo:
        await connector.get_application("demo")

    await connector.client.aclose()
    assert excinfo.value.status_code == 0
    assert "connection refused" in excinfo.value.message
