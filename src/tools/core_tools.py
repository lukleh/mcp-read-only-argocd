"""Core MCP tools for connection management and health checks.

This module provides:
- list_connections: List all available Argo CD connections
- get_version: Get Argo CD version information
- get_settings: Get Argo CD settings
"""

import json
from typing import Dict

from mcp.server.fastmcp import FastMCP

from ..config import ArgoCDConnection
from ..argocd_connector import ArgoCDConnector
from ..validation import get_connector


def register_core_tools(
    mcp: FastMCP,
    connectors: Dict[str, ArgoCDConnector],
    connections: Dict[str, ArgoCDConnection],
) -> None:
    """Register core MCP tools for connection management.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to ArgoCDConnector instances
        connections: Dictionary mapping connection names to ArgoCDConnection configs
    """

    @mcp.tool()
    async def list_connections() -> str:
        """
        List all available Argo CD connections with their configuration details.

        Returns:
            JSON string with connection details including name, url, and description.
        """
        if not connections:
            return json.dumps({"message": "No connections configured"}, indent=2)

        conn_list = []
        for name, conn in connections.items():
            conn_info = {
                "name": name,
                "url": str(conn.url),
                "description": conn.description,
                "timeout": conn.timeout,
                "verify_ssl": conn.verify_ssl,
            }
            conn_list.append(conn_info)

        return json.dumps(conn_list, indent=2)

    @mcp.tool()
    async def get_version(connection_name: str) -> str:
        """
        Get Argo CD version information.

        Args:
            connection_name: Name of the Argo CD connection to check

        Returns:
            JSON string with version information.
        """
        connector = get_connector(connectors, connection_name)
        version = await connector.get_version()
        return json.dumps(version, indent=2)

    @mcp.tool()
    async def get_settings(connection_name: str) -> str:
        """
        Get Argo CD settings.

        Args:
            connection_name: Name of the Argo CD connection

        Returns:
            JSON string with Argo CD settings.
        """
        connector = get_connector(connectors, connection_name)
        settings = await connector.get_settings()
        return json.dumps(settings, indent=2)
