"""Repository MCP tools for Argo CD.

This module provides:
- list_repositories: List all configured repositories
- get_repository: Get repository details
"""

import json
from typing import Dict

from mcp.server.fastmcp import FastMCP

from ..argocd_connector import ArgoCDConnector
from ..validation import get_connector


def register_repository_tools(
    mcp: FastMCP,
    connectors: Dict[str, ArgoCDConnector],
) -> None:
    """Register repository MCP tools.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to ArgoCDConnector instances
    """

    @mcp.tool()
    async def list_repositories(connection_name: str) -> str:
        """
        List all repositories configured in Argo CD.

        Args:
            connection_name: Name of the Argo CD connection

        Returns:
            JSON string with list of repositories including URLs and connection status.
        """
        connector = get_connector(connectors, connection_name)
        repos = await connector.list_repositories()
        return json.dumps(repos, indent=2)

    @mcp.tool()
    async def get_repository(connection_name: str, repo: str) -> str:
        """
        Get detailed information about a specific repository.

        Args:
            connection_name: Name of the Argo CD connection
            repo: Repository URL (e.g., "https://github.com/org/repo")

        Returns:
            JSON string with repository details including connection status and type.
        """
        connector = get_connector(connectors, connection_name)
        repository = await connector.get_repository(repo)
        return json.dumps(repository, indent=2)
