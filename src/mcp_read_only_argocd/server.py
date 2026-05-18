#!/usr/bin/env python3
"""
MCP Read-Only Argo CD Server
Provides secure read-only access to Argo CD instances via MCP protocol.
Uses browser session cookies for authentication.
"""

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from textwrap import dedent
from typing import TypeVar

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
ConfigMarker = tuple[int, int] | None
T = TypeVar("T")


class ReloadableMapping(Mapping[str, T]):
    """Mapping proxy that refreshes connection state before reads."""

    def __init__(
        self,
        refresh: Callable[[], None],
        backing_map: Callable[[], Mapping[str, T]],
    ):
        self._refresh = refresh
        self._backing_map = backing_map

    def _current(self) -> Mapping[str, T]:
        self._refresh()
        return self._backing_map()

    def __getitem__(self, key: str) -> T:
        return self._current()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._current())

    def __len__(self) -> int:
        return len(self._current())

    def __contains__(self, key: object) -> bool:
        return key in self._current()

    def items(self):
        return self._current().items()

    def keys(self):
        return self._current().keys()

    def values(self):
        return self._current().values()


SAMPLE_CONNECTIONS_YAML = dedent("""
    # MCP Read-Only Argo CD Server - Connection Configuration Sample
    # Edit this file to configure your Argo CD connections.
    # Default runtime location: ~/.config/lukleh/mcp-read-only-argocd/connections.yaml

    # Staging Argo CD instance
    - connection_name: staging
      url: https://argocd.example.com
      description: Staging Argo CD instance
      session_token: change_me
      # Optional: override default timeout (30 seconds)
      # timeout: 60

    # Production Argo CD instance
    - connection_name: production
      url: https://argocd-prod.example.com
      description: Production environment Argo CD
      session_token: change_me
      # Optional settings:
      # timeout: 30
      # verify_ssl: true  # Set to false for self-signed certificates (not recommended)

    # Local development Argo CD
    - connection_name: local
      url: http://localhost:8080
      description: Local development Argo CD
      session_token: change_me
      # For local instances, you might want to disable SSL verification
      verify_ssl: false

    # Notes:
    # - To get your session token:
    #     1. Log into Argo CD web UI
    #     2. Open browser developer tools (F12)
    #     3. Go to Application tab -> Cookies
    #     4. Copy the value of 'argocd.token' cookie
    #
    # - Store that cookie value in the session_token field for each connection
    # - Connection names should use only letters, numbers, underscores, and hyphens
    # - URLs should not include trailing slashes
    # - Changes to this file are detected before tool calls, without restarting the MCP
    # - If both sources contain a token, the persisted session state wins until you update or remove it
    """).lstrip()


class ReadOnlyArgoCDServer:
    """MCP Read-Only Argo CD Server using FastMCP."""

    def __init__(self, runtime_paths: RuntimePaths):
        self.runtime_paths = runtime_paths
        self._connections: dict[str, ArgoCDConnection] = {}
        self._connectors: dict[str, ArgoCDConnector] = {}
        self._connections_config_marker: ConfigMarker = None
        self._retired_connectors: list[ArgoCDConnector] = []
        self.connections: Mapping[str, ArgoCDConnection] = ReloadableMapping(
            self._reload_connections_if_needed,
            lambda: self._connections,
        )
        self.connectors: Mapping[str, ArgoCDConnector] = ReloadableMapping(
            self._reload_connections_if_needed,
            lambda: self._connectors,
        )

        self.mcp = FastMCP("mcp-read-only-argocd")

        self._load_connections()
        self._register_tools()

    def _load_connections(self) -> None:
        try:
            connections, connectors, marker = self._build_connections()
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

        self._replace_active_connections(connections, connectors, marker)

    def _read_connections_config_marker(self) -> ConfigMarker:
        """Return a lightweight marker for the current connections.yaml state."""
        try:
            stat_result = self.runtime_paths.connections_file.stat()
        except FileNotFoundError:
            return None
        return (stat_result.st_mtime_ns, stat_result.st_size)

    def _read_connections_config_snapshot(self) -> tuple[str, ConfigMarker]:
        """Read connections.yaml once and return its content with a matching marker."""
        config_path = self.runtime_paths.connections_file.expanduser()
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                yaml_text = handle.read()
                stat_result = os.fstat(handle.fileno())
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Configuration file not found: {self.runtime_paths.connections_file}"
            ) from exc
        return yaml_text, (stat_result.st_mtime_ns, stat_result.st_size)

    @staticmethod
    def _connector_settings_changed(
        existing: ArgoCDConnection,
        updated: ArgoCDConnection,
    ) -> bool:
        """Return True when a connection change requires a new HTTP client."""
        return (
            str(existing.url),
            existing.timeout,
            existing.verify_ssl,
        ) != (
            str(updated.url),
            updated.timeout,
            updated.verify_ssl,
        )

    def _build_connections(
        self,
    ) -> tuple[dict[str, ArgoCDConnection], dict[str, ArgoCDConnector], ConfigMarker]:
        """Build fresh connection and connector maps from one config snapshot."""
        yaml_text, marker = self._read_connections_config_snapshot()
        parser = ConfigParser(
            self.runtime_paths.connections_file,
            state_path=self.runtime_paths.state_file,
        )
        loaded_connections = parser.load_config_from_text(yaml_text)
        built_connections: dict[str, ArgoCDConnection] = {}
        built_connectors: dict[str, ArgoCDConnector] = {}

        for connection in loaded_connections:
            conn_name = connection.connection_name
            existing_connection = self._connections.get(conn_name)
            existing_connector = self._connectors.get(conn_name)

            if (
                existing_connection is not None
                and existing_connector is not None
                and not self._connector_settings_changed(
                    existing_connection, connection
                )
            ):
                connector = existing_connector
            else:
                connector = ArgoCDConnector(connection)

            built_connections[conn_name] = connection
            built_connectors[conn_name] = connector
            logger.info(
                "Loaded connection: %s (%s)",
                conn_name,
                connection.url,
            )

        return built_connections, built_connectors, marker

    def _replace_active_connections(
        self,
        connections: dict[str, ArgoCDConnection],
        connectors: dict[str, ArgoCDConnector],
        marker: ConfigMarker,
    ) -> None:
        """Swap in freshly loaded connections while preserving in-flight clients."""
        previous_retired_connectors = self._retired_connectors
        retired_connectors = [
            connector
            for name, connector in self._connectors.items()
            if connectors.get(name) is not connector
        ]
        self._retired_connectors = retired_connectors
        self._connections = connections
        self._connectors = connectors
        self._connections_config_marker = marker

        # Update reused connectors only after the reload succeeded fully.
        for name, connector in self._connectors.items():
            connector.connection = self._connections[name]

        for connector in previous_retired_connectors:
            self._schedule_connector_close(connector)

    @staticmethod
    def _schedule_connector_close(connector: ArgoCDConnector) -> None:
        """Close retired connectors in the background when an event loop is active."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(connector.close())

    def _reload_connections_if_needed(self) -> None:
        """Reload connections.yaml when it changes, keeping the last good config."""
        previous_marker = self._connections_config_marker
        current_marker = self._read_connections_config_marker()

        if current_marker == previous_marker:
            return

        logger.info(
            "Detected change in %s; reloading connections",
            self.runtime_paths.connections_file,
        )
        try:
            connections, connectors, marker = self._build_connections()
        except Exception as exc:
            logger.warning(
                "Failed to reload configuration from %s; keeping %s previously loaded connection(s): %s",
                self.runtime_paths.connections_file,
                len(self._connections),
                exc,
            )
            return

        self._replace_active_connections(connections, connectors, marker)
        logger.info(
            "Reloaded %s Argo CD connection(s) from %s",
            len(self._connections),
            self.runtime_paths.connections_file,
        )

    def _register_tools(self) -> None:
        register_core_tools(self.mcp, self.connectors, self.connections)
        register_application_tools(self.mcp, self.connectors)
        register_project_tools(self.mcp, self.connectors)
        register_cluster_tools(self.mcp, self.connectors)
        register_repository_tools(self.mcp, self.connectors)

    async def cleanup(self) -> None:
        seen: set[int] = set()
        for connector in [*self._connectors.values(), *self._retired_connectors]:
            connector_id = id(connector)
            if connector_id in seen:
                continue
            seen.add(connector_id)
            await connector.close()

    def run(self) -> None:
        if not self.connections:
            logger.warning(
                "No connections loaded. Server will run with limited functionality."
            )
        else:
            logger.info("Loaded %s Argo CD connection(s)", len(self.connections))

        self.mcp.run()


def write_sample_config(
    runtime_paths: RuntimePaths, *, overwrite: bool = False
) -> Path:
    """Write a sample connections.yaml for package-based installs."""
    runtime_paths.ensure_directories()

    config_path = runtime_paths.connections_file
    if config_path.exists() and not overwrite:
        raise FileExistsError(
            f"Config file already exists at {config_path}. Re-run with --overwrite to replace it."
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
        "--overwrite",
        action="store_true",
        help="Replace connections.yaml when used with --write-sample-config",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.overwrite and not args.write_sample_config:
        parser.error("--overwrite can only be used with --write-sample-config")

    runtime_paths = resolve_runtime_paths(
        config_dir=args.config_dir,
        state_dir=args.state_dir,
        cache_dir=args.cache_dir,
    )

    if args.write_sample_config:
        try:
            config_path = write_sample_config(runtime_paths, overwrite=args.overwrite)
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
