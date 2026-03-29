# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP Read-Only Argo CD Server provides read-only access to Argo CD instances via the Model Context Protocol (MCP). It uses browser session cookie authentication and supports multiple Argo CD connections simultaneously.

## Development Commands

```bash
# Install dependencies
uv sync --extra dev

# Run the server manually for testing
uv run python -m mcp_read_only_argocd.server

# Show runtime paths or write the sample config
uv run mcp-read-only-argocd --print-paths
uv run mcp-read-only-argocd --write-sample-config

# Smoke test all configured connections
uv run python smoke_test.py

# Smoke test a specific connection
uv run python smoke_test.py --connection staging

# Code formatting
uv run black src/mcp_read_only_argocd/
uv run ruff check src/mcp_read_only_argocd/ tests/ smoke_test.py

# Run tests
uv run pytest
```

## Architecture

### Core Components

**src/mcp_read_only_argocd/server.py** - MCP server entry point
- `ReadOnlyArgoCDServer` class manages connections and orchestrates tool registration
- Calls domain-specific registration functions from `src/mcp_read_only_argocd/tools/`
- Error handling: Let exceptions propagate naturally - the MCP framework handles them

**src/mcp_read_only_argocd/config.py** - Configuration management
- `ArgoCDConnection` (Pydantic model): Validates connection settings
- `ConfigParser`: Loads connections from YAML and environment variables
- Session token pattern: `ARGOCD_SESSION_<CONNECTION_NAME>` (uppercase, hyphens→underscores)
- **Dynamic token reloading**: `reload_session_token()` reloads the runtime environment and persisted session cache on every call

**src/mcp_read_only_argocd/argocd_connector.py** - Argo CD API client
- `ArgoCDConnector` wraps httpx for Argo CD API calls
- **Critical**: `_get()` calls `_refresh_credentials()` before EVERY request
- This reloads the configured credential sources without restarting the server
- Automatic cookie rotation: captures refreshed `argocd.token` from response headers

**src/mcp_read_only_argocd/exceptions.py** - Custom exception hierarchy
- `ArgoCDError` (base), `ConnectionNotFoundError`, `AuthenticationError`
- `PermissionDeniedError`, `ArgoCDAPIError`, `ArgoCDTimeoutError`

**src/mcp_read_only_argocd/validation.py** - Validation utilities
- `get_connector()`: Centralizes connection validation

### Tool Organization

Tools are organized into domain-specific modules under `src/mcp_read_only_argocd/tools/`:

| Module | Tools | Description |
|--------|-------|-------------|
| `core_tools.py` | `list_connections`, `get_version`, `get_settings` | Connection management |
| `application_tools.py` | 5 tools | Applications, resources, logs |
| `project_tools.py` | 2 tools | Argo CD projects |
| `cluster_tools.py` | 2 tools | Registered clusters |
| `repository_tools.py` | 2 tools | Git repositories |

Each module exports a `register_*_tools(mcp, connectors)` function.

### Configuration Flow

1. `ConfigParser.load_config()` reads `connections.yaml`
2. For each connection, `_process_connection()` creates an `ArgoCDConnection`
3. Session tokens are loaded from environment variables at startup
4. On each API request, `reload_session_token()` re-reads the runtime environment and persisted session cache; persisted state overrides the live environment value when both are present

### Error Handling Pattern

Custom exceptions in `src/mcp_read_only_argocd/exceptions.py` provide clear, typed errors:
- `ConnectionNotFoundError`: Invalid connection name (shows available options)
- `AuthenticationError`: HTTP 401, expired session
- `PermissionDeniedError`: HTTP 403, insufficient permissions
- `ArgoCDAPIError`: Other HTTP errors with status code
- `ArgoCDTimeoutError`: Request timeout

The MCP framework automatically converts exceptions to proper error responses.
Tool functions use `get_connector()` for validation instead of manual checks.

### Authentication

Session-based authentication using Argo CD browser cookies:
- Tokens are injected via environment variables (never in code or YAML)
- Tokens are reloaded from the runtime environment before each request, but persisted rotated state takes precedence
- Automatic capture and persistence of rotated tokens from Set-Cookie headers
- Connection name in YAML maps to `ARGOCD_SESSION_<NAME>` in environment

## Key Design Decisions

1. **Read-only by design**: Only GET requests are performed
2. **Session token reload**: Tokens are reloaded from the configured credential sources on every request
3. **No credential storage in YAML**: Tokens are injected via environment variables and may be cached in the local session state file
4. **Multiple instance support**: Each connection has its own connector with independent configuration
5. **MCP error handling**: Let exceptions propagate; framework handles them properly
6. **NDJSON log parsing**: Argo CD log endpoints return newline-delimited JSON; the connector parses this automatically
