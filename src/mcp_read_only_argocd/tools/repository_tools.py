"""Repository MCP tools for Argo CD.

This module provides:
- list_repositories: List all configured repositories
- get_repository: Get repository details
"""

from collections.abc import Mapping

from mcp.server.mcpserver import MCPServer

from ..argocd_connector import ArgoCDConnector
from ..validation import get_connector, render_tool_result


def register_repository_tools(
    mcp: MCPServer,
    connectors: Mapping[str, ArgoCDConnector],
) -> None:
    """Register repository MCP tools.

    Args:
        mcp: MCPServer server instance
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
        return await render_tool_result(connector.list_repositories())

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
        return await render_tool_result(connector.get_repository(repo))
