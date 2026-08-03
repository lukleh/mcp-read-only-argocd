"""Project MCP tools for Argo CD.

This module provides:
- list_projects: List all projects
- get_project: Get project details
"""

from collections.abc import Mapping

from mcp.server.mcpserver import MCPServer

from ..argocd_connector import ArgoCDConnector
from ..validation import get_connector, render_tool_result


def register_project_tools(
    mcp: MCPServer,
    connectors: Mapping[str, ArgoCDConnector],
) -> None:
    """Register project MCP tools.

    Args:
        mcp: MCPServer server instance
        connectors: Dictionary mapping connection names to ArgoCDConnector instances
    """

    @mcp.tool()
    async def list_projects(connection_name: str) -> str:
        """
        List all projects in Argo CD.

        Projects define the scope of resources an application can deploy.

        Args:
            connection_name: Name of the Argo CD connection

        Returns:
            JSON string with list of projects.
        """
        connector = get_connector(connectors, connection_name)
        return await render_tool_result(connector.list_projects())

    @mcp.tool()
    async def get_project(connection_name: str, name: str) -> str:
        """
        Get detailed information about a specific project.

        Args:
            connection_name: Name of the Argo CD connection
            name: Project name

        Returns:
            JSON string with project details including source repos, destinations, and roles.
        """
        connector = get_connector(connectors, connection_name)
        return await render_tool_result(connector.get_project(name))
