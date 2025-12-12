#!/usr/bin/env python3
"""
MCP Read-Only Argo CD Server
Provides secure read-only access to Argo CD instances via MCP protocol.
Uses browser session cookies for authentication.
"""

import argparse
import logging
import sys
from typing import Dict

from mcp.server.fastmcp import FastMCP

from .config import ConfigParser, ArgoCDConnection
from .argocd_connector import ArgoCDConnector
from .tools import (
    register_core_tools,
    register_application_tools,
    register_project_tools,
    register_cluster_tools,
    register_repository_tools,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class ReadOnlyArgoCDServer:
    """MCP Read-Only Argo CD Server using FastMCP"""

    def __init__(self, config_path: str = "connections.yaml"):
        """Initialize the server with configuration

        Args:
            config_path: Path to the connections.yaml configuration file
        """
        self.config_path = config_path
        self.connections: Dict[str, ArgoCDConnection] = {}
        self.connectors: Dict[str, ArgoCDConnector] = {}

        # Initialize FastMCP server
        self.mcp = FastMCP("mcp-read-only-argocd")

        # Load connections
        self._load_connections()

        # Register tools from domain modules
        self._register_tools()

    def _load_connections(self):
        """Load all connections from config file"""
        parser = ConfigParser(self.config_path)

        try:
            connections = parser.load_config()
        except FileNotFoundError:
            logger.warning(f"Configuration file not found: {self.config_path}")
            logger.info(
                "Please create a connections.yaml file from connections.yaml.sample"
            )
            return
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

        for conn in connections:
            self.connections[conn.connection_name] = conn
            self.connectors[conn.connection_name] = ArgoCDConnector(conn)
            logger.info(f"Loaded connection: {conn.connection_name} ({conn.url})")

    def _register_tools(self):
        """Register all MCP tools organized by domain."""
        # Core tools (list_connections, get_version, get_settings)
        register_core_tools(self.mcp, self.connectors, self.connections)

        # Application tools
        register_application_tools(self.mcp, self.connectors)

        # Project tools
        register_project_tools(self.mcp, self.connectors)

        # Cluster tools
        register_cluster_tools(self.mcp, self.connectors)

        # Repository tools
        register_repository_tools(self.mcp, self.connectors)

    async def cleanup(self):
        """Clean up resources"""
        for connector in self.connectors.values():
            await connector.close()

    def run(self):
        """Run the FastMCP server"""
        if not self.connections:
            logger.warning(
                "No connections loaded. Server will run with limited functionality."
            )
        else:
            logger.info(f"Loaded {len(self.connections)} Argo CD connection(s)")

        # Run the FastMCP server (defaults to stdio transport)
        self.mcp.run()


def main():
    """Main entry point for the MCP server"""
    parser = argparse.ArgumentParser(
        description="MCP Read-Only Argo CD Server - Secure read-only access to Argo CD instances using browser session cookies"
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="connections.yaml",
        help="Path to connections.yaml configuration file (default: connections.yaml)",
    )

    args = parser.parse_args()

    # Create and run server
    server = ReadOnlyArgoCDServer(config_path=args.config)

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
