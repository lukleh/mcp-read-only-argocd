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

from .argocd_connector import ArgoCDConnector
from .config import ArgoCDConnection, ConfigParser
from .runtime_paths import resolve_runtime_paths, RuntimePaths
from .tools import (
    register_application_tools,
    register_cluster_tools,
    register_core_tools,
    register_project_tools,
    register_repository_tools,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class ReadOnlyArgoCDServer:
    """MCP Read-Only Argo CD Server using FastMCP."""

    def __init__(self, runtime_paths: RuntimePaths):
        self.runtime_paths = runtime_paths
        self.connections: Dict[str, ArgoCDConnection] = {}
        self.connectors: Dict[str, ArgoCDConnector] = {}

        self.mcp = FastMCP("mcp-read-only-argocd")

        self._load_connections()
        self._register_tools()

    def _load_connections(self) -> None:
        parser = ConfigParser(
            self.runtime_paths.connections_file,
            state_path=self.runtime_paths.state_file,
        )

        try:
            connections = parser.load_config()
        except FileNotFoundError:
            logger.warning(
                "Configuration file not found: %s",
                self.runtime_paths.connections_file,
            )
            logger.info("Expected Argo CD config at %s", self.runtime_paths.config_dir)
            return
        except Exception as exc:
            logger.error("Failed to load configuration: %s", exc)
            raise

        for connection in connections:
            self.connections[connection.connection_name] = connection
            self.connectors[connection.connection_name] = ArgoCDConnector(connection)
            logger.info(
                "Loaded connection: %s (%s)",
                connection.connection_name,
                connection.url,
            )

    def _register_tools(self) -> None:
        register_core_tools(self.mcp, self.connectors, self.connections)
        register_application_tools(self.mcp, self.connectors)
        register_project_tools(self.mcp, self.connectors)
        register_cluster_tools(self.mcp, self.connectors)
        register_repository_tools(self.mcp, self.connectors)

    async def cleanup(self) -> None:
        for connector in self.connectors.values():
            await connector.close()

    def run(self) -> None:
        if not self.connections:
            logger.warning(
                "No connections loaded. Server will run with limited functionality."
            )
        else:
            logger.info("Loaded %s Argo CD connection(s)", len(self.connections))

        self.mcp.run()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MCP Read-Only Argo CD Server - Secure read-only access to Argo CD "
            "instances using browser session cookies"
        )
    )
    parser.add_argument(
        "--config-dir",
        help="Directory containing connections.yaml",
    )
    parser.add_argument(
        "--state-dir",
        help="Directory containing session_tokens.json",
    )
    parser.add_argument(
        "--cache-dir",
        help="Directory reserved for cache files",
    )
    parser.add_argument(
        "--print-paths",
        action="store_true",
        help="Print resolved config/state/cache paths and exit",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    runtime_paths = resolve_runtime_paths(
        config_dir=args.config_dir,
        state_dir=args.state_dir,
        cache_dir=args.cache_dir,
    )

    if args.print_paths:
        print(runtime_paths.render())
        return

    server = ReadOnlyArgoCDServer(runtime_paths=runtime_paths)

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as exc:
        logger.error("Server error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
