"""MCP tool modules organized by domain.

This package contains domain-specific tool registration functions
that are called by the main server to register all MCP tools.

Modules:
    core_tools: Connection management and health checks
    application_tools: Application listing and details
    project_tools: Project listing and details
    cluster_tools: Cluster listing and details
    repository_tools: Repository listing and details
"""

from .core_tools import register_core_tools
from .application_tools import register_application_tools
from .project_tools import register_project_tools
from .cluster_tools import register_cluster_tools
from .repository_tools import register_repository_tools

__all__ = [
    "register_core_tools",
    "register_application_tools",
    "register_project_tools",
    "register_cluster_tools",
    "register_repository_tools",
]
