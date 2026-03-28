#!/usr/bin/env python3
"""
MCP Read-Only Argo CD Server
Provides secure read-only access to Argo CD instances via MCP protocol.
Uses browser session cookies for authentication.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from textwrap import dedent
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
SAMPLE_CONNECTIONS_YAML = dedent(
    """
    # MCP Read-Only Argo CD Server - Connection Configuration Sample
    # Copy this file to ~/.config/lukleh/mcp-read-only-argocd/connections.yaml

    # Staging Argo CD instance
    - connection_name: staging
      url: https://argocd.example.com
      description: Staging Argo CD instance
      # Optional: override default timeout (30 seconds)
      # timeout: 60

    # Production Argo CD instance
    - connection_name: production
      url: https://argocd-prod.example.com
      description: Production environment Argo CD
      # Optional settings:
      # timeout: 30
      # verify_ssl: true  # Set to false for self-signed certificates (not recommended)

    # Local development Argo CD
    - connection_name: local
      url: http://localhost:8080
      description: Local development Argo CD
      # For local instances, you might want to disable SSL verification
      verify_ssl: false

    # Notes:
    # - Session tokens are read from environment variables:
    #     ARGOCD_SESSION_<CONNECTION_NAME> (e.g., ARGOCD_SESSION_STAGING)
    #
    # - To get your session token:
    #     1. Log into Argo CD web UI
    #     2. Open browser developer tools (F12)
    #     3. Go to Application tab -> Cookies
    #     4. Copy the value of 'argocd.token' cookie
    #
    # - Connection names should use only letters, numbers, underscores, and hyphens
    # - URLs should not include trailing slashes
    # - Credentials are reloaded from the runtime environment and persisted session state before each request to support token rotation
    # - If both sources contain a token, the persisted session state wins until you update or remove it
    """
).lstrip()


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


def write_sample_config(runtime_paths: RuntimePaths, *, force: bool = False) -> Path:
    """Write a sample connections.yaml for package-based installs."""
    runtime_paths.ensure_directories()

    config_path = runtime_paths.connections_file
    if config_path.exists() and not force:
        raise FileExistsError(
            f"Config file already exists at {config_path}. Re-run with --force to overwrite it."
        )

    config_path.write_text(SAMPLE_CONNECTIONS_YAML, encoding="utf-8")
    return config_path


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
    parser.add_argument(
        "--write-sample-config",
        action="store_true",
        help="Write a sample connections.yaml to the resolved config path and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite connections.yaml when used with --write-sample-config",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.force and not args.write_sample_config:
        parser.error("--force can only be used with --write-sample-config")

    runtime_paths = resolve_runtime_paths(
        config_dir=args.config_dir,
        state_dir=args.state_dir,
        cache_dir=args.cache_dir,
    )

    if args.write_sample_config:
        try:
            config_path = write_sample_config(runtime_paths, force=args.force)
        except FileExistsError as exc:
            parser.error(str(exc))
        print(f"Wrote sample config to {config_path}")
        if not args.print_paths:
            return

    if args.print_paths:
        print(runtime_paths.render())
        return

    server = ReadOnlyArgoCDServer(runtime_paths=runtime_paths)
    exit_code = 0

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as exc:
        logger.error("Server error: %s", exc)
        exit_code = 1
    finally:
        try:
            asyncio.run(server.cleanup())
        except Exception as cleanup_exc:
            logger.warning("Error during shutdown cleanup: %s", cleanup_exc)

    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
