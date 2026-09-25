"""Validation utilities for MCP tools.

This module provides helper functions that centralize common validation
patterns used across all MCP tool functions.
"""

import functools
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, ParamSpec, TypeVar

from mcp import MCPError
from mcp.server.mcpserver.exceptions import ToolError

from .argocd_connector import ArgoCDConnector
from .exceptions import ArgoCDError, AuthenticationError, ConnectionNotFoundError

P = ParamSpec("P")
R = TypeVar("R")

# Exception types the tools raise for failures the caller can act on: an Argo CD
# error (unknown connection, 403, other HTTP status, transport failure, timeout),
# a missing session token or unparseable response (ValueError), or a problem
# persisting a rotated token to connections.yaml (OSError). Anything else is a
# bug and stays a crash.
ANTICIPATED_TOOL_ERRORS: tuple[type[Exception], ...] = (
    ArgoCDError,
    ValueError,
    OSError,
)


def surface_tool_errors(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Report an anticipated tool failure to the caller with its message.

    Since mcp 2.1 the SDK treats any exception other than ``ToolError`` (or a
    protocol-level ``MCPError``) as a crash and replaces its text with the
    generic ``Error executing tool <name>``. The failures listed in
    ``ANTICIPATED_TOOL_ERRORS`` are re-raised as ``ToolError`` so the caller
    sees the reason. Anything else keeps the SDK's crash handling: the text
    stays on the server, logged with its traceback.

    Apply it below ``@mcp.tool()`` on every tool. ``functools.wraps`` keeps the
    signature and docstring the SDK reads to build the tool schema.
    """

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except (ToolError, MCPError):
            raise
        except ANTICIPATED_TOOL_ERRORS as exc:
            raise ToolError(str(exc) or type(exc).__name__) from exc

    return wrapper


def get_connector(
    connectors: Mapping[str, ArgoCDConnector],
    connection_name: str,
) -> ArgoCDConnector:
    """Get a connector by name or raise ConnectionNotFoundError.

    Args:
        connectors: Dictionary mapping connection names to ArgoCDConnector instances.
        connection_name: The name of the connection to retrieve.

    Returns:
        The ArgoCDConnector for the specified connection.

    Raises:
        ConnectionNotFoundError: If connection_name is not in connectors.

    Example:
        ```python
        @mcp.tool()
        async def list_applications(connection_name: str) -> str:
            connector = get_connector(connectors, connection_name)
            apps = await connector.list_applications()
            return json.dumps(apps, indent=2)
        ```
    """
    if connection_name not in connectors:
        raise ConnectionNotFoundError(
            connection_name=connection_name,
            available=list(connectors.keys()),
        )
    return connectors[connection_name]


async def render_tool_result(operation: Awaitable[Any]) -> str:
    """Serialize tool results, returning auth failures as normal JSON payloads."""
    try:
        result = await operation
    except AuthenticationError as exc:
        result = {
            "error": "authentication_failed",
            "connection_name": exc.connection_name,
            "message": str(exc),
            "next_step": (
                "Log in to the Argo CD web UI in Chrome Profile 1, then retry the "
                "tool call. If that still fails, update session_token in connections.yaml."
            ),
        }

    return json.dumps(result, indent=2)
