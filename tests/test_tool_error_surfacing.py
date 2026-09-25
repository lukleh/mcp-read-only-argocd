"""Tests for the tool-boundary error translation under mcp SDK 2.x."""

import inspect
from pathlib import Path

import httpx
import pytest
import yaml
from mcp import MCPError
from mcp.client import Client
from mcp.server.mcpserver.exceptions import ToolError

from mcp_read_only_argocd.exceptions import (
    ArgoCDAPIError,
    ArgoCDError,
    ArgoCDTimeoutError,
    ConnectionNotFoundError,
    PermissionDeniedError,
)
from mcp_read_only_argocd.runtime_paths import RuntimePaths
from mcp_read_only_argocd.server import ReadOnlyArgoCDServer
from mcp_read_only_argocd.validation import (
    ANTICIPATED_TOOL_ERRORS,
    surface_tool_errors,
)


def _raising(exc: BaseException):
    @surface_tool_errors
    async def tool() -> str:
        raise exc

    return tool


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionNotFoundError("alpha", ["beta"]),
        PermissionDeniedError("beta", "read"),
        ArgoCDAPIError(404, "application not found", "beta"),
        ArgoCDAPIError(0, "Request error: All connection attempts failed", "beta"),
        ArgoCDTimeoutError(30, "beta"),
        ValueError("Missing session token for connection 'beta'."),
        PermissionError("connections.yaml is not writable"),
    ],
)
async def test_anticipated_failures_become_tool_errors(exc):
    """Operational failures keep their text and their cause."""
    with pytest.raises(ToolError) as info:
        await _raising(exc)()

    assert str(info.value) == str(exc)
    assert info.value.__cause__ is exc


def test_anticipated_list_matches_parametrized_cases():
    """Guard the allow-list against silent drift."""
    assert ANTICIPATED_TOOL_ERRORS == (ArgoCDError, ValueError, OSError)


async def test_empty_message_falls_back_to_class_name():
    """A bare exception still yields a readable result, not an empty one."""
    with pytest.raises(ToolError, match="^ValueError$"):
        await _raising(ValueError())()


@pytest.mark.parametrize("exc_type", [TypeError, AttributeError, KeyError, RuntimeError])
async def test_programming_errors_keep_sdk_crash_handling(exc_type):
    """Bugs propagate unchanged so the SDK masks the text and logs the traceback."""
    with pytest.raises(exc_type):
        await _raising(exc_type("internal detail"))()


async def test_tool_error_passes_through_unchanged():
    """No double wrapping when the body already raised a ToolError."""
    original = ToolError("already anticipated")
    with pytest.raises(ToolError) as info:
        await _raising(original)()

    assert info.value is original


async def test_protocol_error_passes_through_unchanged():
    """MCPError is a protocol error and must not become an is_error result."""
    original = MCPError(-32600, "invalid request")
    with pytest.raises(MCPError) as info:
        await _raising(original)()

    assert info.value is original


def test_wrapper_keeps_the_signature_the_sdk_reads():
    """The tool schema is built from the wrapped function's signature and docstring."""

    async def get_version(connection_name: str, limit: int = 5) -> str:
        """Get the version."""
        return connection_name

    wrapped = surface_tool_errors(get_version)

    assert wrapped.__name__ == "get_version"
    assert wrapped.__doc__ == "Get the version."
    assert inspect.signature(wrapped) == inspect.signature(get_version)
    assert inspect.iscoroutinefunction(wrapped)


def _make_server(tmp_path: Path) -> ReadOnlyArgoCDServer:
    runtime_paths = RuntimePaths(
        config_dir=tmp_path / "config",
        cache_dir=tmp_path / "cache",
    )
    runtime_paths.ensure_directories()
    runtime_paths.connections_file.write_text(
        yaml.safe_dump(
            [
                {
                    "connection_name": "beta",
                    "url": "https://argocd.example.com",
                    "session_token": "beta-token",
                }
            ]
        ),
        encoding="utf-8",
    )
    return ReadOnlyArgoCDServer(runtime_paths)


def test_every_registered_tool_surfaces_errors(tmp_path):
    """A tool registered without the decorator would hide its failures again."""
    wrapper_code = _raising(ValueError()).__code__
    server = _make_server(tmp_path)

    tools = server.mcp._tool_manager.list_tools()
    assert tools
    unwrapped = [tool.name for tool in tools if tool.fn.__code__ is not wrapper_code]
    assert unwrapped == []


async def test_client_sees_unknown_connection_message(tmp_path):
    """The reason reaches the caller through the in-process client."""
    server = _make_server(tmp_path)

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_version", {"connection_name": "alpha"})

    assert result.is_error
    assert result.content[0].text == (
        "Error executing tool get_version: Connection 'alpha' not found. "
        "Available connections: beta"
    )


async def test_client_sees_argocd_http_error(tmp_path):
    """An HTTP error from Argo CD reaches the caller with its status and body."""
    server = _make_server(tmp_path)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="application not found")

    connector = server.connectors["beta"]
    await connector.client.aclose()
    connector.client = httpx.AsyncClient(
        base_url="https://argocd.example.com",
        transport=httpx.MockTransport(handler),
    )

    try:
        async with Client(server.mcp) as client:
            result = await client.call_tool(
                "get_application",
                {"connection_name": "beta", "name": "missing"},
            )
    finally:
        await server.cleanup()

    assert result.is_error
    assert result.content[0].text == (
        "Error executing tool get_application: [beta] HTTP 404: application not found"
    )
