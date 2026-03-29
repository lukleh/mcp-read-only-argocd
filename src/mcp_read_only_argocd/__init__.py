"""MCP Read-Only Argo CD Server - Secure read-only access to Argo CD instances."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-read-only-argocd")
except PackageNotFoundError:
    __version__ = "0+unknown"
