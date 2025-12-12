"""Cluster MCP tools for Argo CD.

This module provides:
- list_clusters: List all registered clusters
- get_cluster: Get cluster details
"""

import json
from typing import Dict

from mcp.server.fastmcp import FastMCP

from ..argocd_connector import ArgoCDConnector
from ..validation import get_connector


def register_cluster_tools(
    mcp: FastMCP,
    connectors: Dict[str, ArgoCDConnector],
) -> None:
    """Register cluster MCP tools.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to ArgoCDConnector instances
    """

    @mcp.tool()
    async def list_clusters(connection_name: str) -> str:
        """
        List all clusters registered in Argo CD.

        Args:
            connection_name: Name of the Argo CD connection

        Returns:
            JSON string with list of clusters including server URLs and connection status.
        """
        connector = get_connector(connectors, connection_name)
        clusters = await connector.list_clusters()
        return json.dumps(clusters, indent=2)

    @mcp.tool()
    async def get_cluster(connection_name: str, server: str) -> str:
        """
        Get detailed information about a specific cluster.

        Args:
            connection_name: Name of the Argo CD connection
            server: Cluster server URL (e.g., "https://kubernetes.default.svc")

        Returns:
            JSON string with cluster details including connection info and namespaces.
        """
        connector = get_connector(connectors, connection_name)
        cluster = await connector.get_cluster(server)
        return json.dumps(cluster, indent=2)
