"""Application MCP tools for Argo CD.

This module provides:
- list_applications: List all applications
- get_application: Get application details
- get_application_resource_tree: Get Kubernetes resource tree
- get_application_managed_resources: Get managed resources
- get_application_logs: Get application logs
"""

from collections.abc import Mapping

from mcp.server.mcpserver import MCPServer

from ..argocd_connector import ArgoCDConnector
from ..validation import get_connector, render_tool_result


def register_application_tools(
    mcp: MCPServer,
    connectors: Mapping[str, ArgoCDConnector],
) -> None:
    """Register application MCP tools.

    Args:
        mcp: MCPServer instance
        connectors: Dictionary mapping connection names to ArgoCDConnector instances
    """

    @mcp.tool()
    async def list_applications(
        connection_name: str,
        projects: list[str] | None = None,
        selector: str | None = None,
    ) -> str:
        """
        List all applications in Argo CD.

        Args:
            connection_name: Name of the Argo CD connection
            projects: Optional list of project names to filter by
            selector: Optional label selector to filter applications (e.g., "app=myapp")

        Returns:
            JSON string with list of applications.
        """
        connector = get_connector(connectors, connection_name)
        return await render_tool_result(
            connector.list_applications(projects=projects, selector=selector)
        )

    @mcp.tool()
    async def get_application(connection_name: str, name: str) -> str:
        """
        Get detailed information about a specific application.

        Args:
            connection_name: Name of the Argo CD connection
            name: Application name

        Returns:
            JSON string with application details including sync status, health, and spec.
        """
        connector = get_connector(connectors, connection_name)
        return await render_tool_result(connector.get_application(name))

    @mcp.tool()
    async def get_application_resource_tree(connection_name: str, name: str) -> str:
        """
        Get the Kubernetes resource tree for an application.

        Shows all resources created by the application and their relationships.

        Args:
            connection_name: Name of the Argo CD connection
            name: Application name

        Returns:
            JSON string with resource tree including nodes and their parent references.
        """
        connector = get_connector(connectors, connection_name)
        return await render_tool_result(connector.get_application_resource_tree(name))

    @mcp.tool()
    async def get_application_managed_resources(
        connection_name: str,
        name: str,
        group: str | None = None,
        kind: str | None = None,
        namespace: str | None = None,
        resource_name: str | None = None,
    ) -> str:
        """
        Get managed resources for an application.

        Args:
            connection_name: Name of the Argo CD connection
            name: Application name
            group: Optional API group to filter (e.g., "apps", "networking.k8s.io")
            kind: Optional resource kind to filter (e.g., "Deployment", "Service")
            namespace: Optional namespace to filter
            resource_name: Optional resource name to filter

        Returns:
            JSON string with list of managed resources.
        """
        connector = get_connector(connectors, connection_name)
        return await render_tool_result(
            connector.get_application_managed_resources(
                name,
                group=group,
                kind=kind,
                namespace=namespace,
                resource_name=resource_name,
            )
        )

    @mcp.tool()
    async def get_application_logs(
        connection_name: str,
        name: str,
        namespace: str | None = None,
        pod_name: str | None = None,
        container: str | None = None,
        tail_lines: int | None = None,
        since_seconds: int | None = None,
    ) -> str:
        """
        Get logs for an application's pods.

        Args:
            connection_name: Name of the Argo CD connection
            name: Application name
            namespace: Optional namespace (defaults to application's namespace)
            pod_name: Optional specific pod name to get logs from
            container: Optional container name within the pod
            tail_lines: Number of lines from the end to return (e.g., 100)
            since_seconds: Return logs from the last N seconds

        Returns:
            JSON string with log entries.
        """
        connector = get_connector(connectors, connection_name)
        return await render_tool_result(
            connector.get_application_logs(
                name,
                namespace=namespace,
                pod_name=pod_name,
                container=container,
                tail_lines=tail_lines,
                since_seconds=since_seconds,
            )
        )
