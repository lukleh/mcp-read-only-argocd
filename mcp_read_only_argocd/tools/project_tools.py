"""Project MCP tools for Argo CD.

This module provides:
- list_projects: List all projects
- get_project: Get project details
"""

import json
from typing import Dict

from mcp.server.fastmcp import FastMCP

from ..argocd_connector import ArgoCDConnector
from ..validation import get_connector


def register_project_tools(
    mcp: FastMCP,
    connectors: Dict[str, ArgoCDConnector],
) -> None:
    """Register project MCP tools.

    Args:
        mcp: FastMCP server instance
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
        projects = await connector.list_projects()
        return json.dumps(projects, indent=2)

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
        project = await connector.get_project(name)
        return json.dumps(project, indent=2)
