"""Validation utilities for MCP tools.

This module provides helper functions that centralize common validation
patterns used across all MCP tool functions.
"""

import json
from collections.abc import Awaitable, Mapping
from typing import Any

from .argocd_connector import ArgoCDConnector
from .exceptions import AuthenticationError, ConnectionNotFoundError


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
