"""Validation utilities for MCP tools.

This module provides helper functions that centralize common validation
patterns used across all MCP tool functions.
"""

from typing import Dict

from .exceptions import ConnectionNotFoundError
from .argocd_connector import ArgoCDConnector


def get_connector(
    connectors: Dict[str, ArgoCDConnector],
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
