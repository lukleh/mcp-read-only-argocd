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

# Linting
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
- `ConfigParser`: Loads connections and session tokens from YAML
- `session_token` is the only credential source; there is no separate state file or environment-variable layer
- **Dynamic token reloading**: the server hot-reloads changed YAML before tool calls, and `reload_session_token()` re-applies the currently loaded value on every request. A rotated token is written back into `connections.yaml` itself (`_persist_token_to_yaml`), matched by `connection_name`

**src/mcp_read_only_argocd/chrome_session.py** - Browser cookie loader
- `load_session_token_from_chrome(url)` reads the `argocd.token` cookie matching a connection's
  host out of the local Chrome cookie store (`Profile 1` by default)
- Normal authentication is the `session_token` pasted into `connections.yaml`; Chrome is only consulted
  as the non-interactive recovery source after a 401, when the configured token has gone stale

**src/mcp_read_only_argocd/argocd_connector.py** - Argo CD API client
- `ArgoCDConnector` wraps httpx for Argo CD API calls
- **Critical**: `_get()` calls `_refresh_credentials()` before EVERY request
- This applies the currently loaded credential sources without restarting the server
- Automatic cookie rotation: captures refreshed `argocd.token` from response headers
- On a 401, `_refresh_credentials_after_auth_failure()` retries once from the non-interactive
  sources in order: a rotated cookie on the response, then a newer `argocd.token` from Chrome. If
  Chrome has no matching cookie, or the same value, the attempt is reported rather than retried

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

Each module exports a `register_*_tools(mcp, connectors)` function; `register_core_tools` also takes the `connections` list.

### Configuration Flow

1. `ConfigParser.load_config()` reads `connections.yaml`
2. For each connection, `_process_connection()` creates an `ArgoCDConnection`
3. Session tokens are loaded from each connection's `session_token` field
4. Tool calls check whether `connections.yaml` changed and keep the last good config if reload fails
5. On each API request, `reload_session_token()` re-applies the currently loaded token; after a successful rotation the new value replaces it both in memory and in `connections.yaml`

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
- Tokens are stored in the local runtime `connections.yaml`
- Changes to runtime `connections.yaml` are hot-reloaded before tool calls
- Tokens are reloaded from the active connection before each request
- Automatic capture and persistence of rotated tokens from Set-Cookie headers
- Rotated tokens are written back into `connections.yaml`, into the entry matching `connection_name`
- A 401 triggers one non-interactive refresh attempt, falling back to the `argocd.token` cookie in
  the local Chrome profile; there is no interactive login path

## Key Design Decisions

1. **Read-only by design**: Only GET requests are performed
2. **Session token reload**: Tokens are reloaded from the configured credential sources on every request
3. **Local YAML credential storage**: Tokens are read from the runtime `connections.yaml`, and rotated tokens are written back to that same file — there is no separate session state file
4. **Multiple instance support**: Each connection has its own connector with independent configuration
5. **MCP error handling**: Let exceptions propagate; framework handles them properly
6. **NDJSON log parsing**: Argo CD log endpoints return newline-delimited JSON; the connector parses this automatically

## Releasing

A merged PR does **not** ship to PyPI on its own — publishing is triggered by pushing a `vX.Y.Z`
git tag, which runs `.github/workflows/publish.yml`. See [`RELEASING.md`](RELEASING.md) for the
authoritative checklist; the short version:

1. **Bump the version** in `pyproject.toml` `[project].version`, then refresh the lockfile:
   `uv sync --extra dev`.
2. **Promote the changelog**: move the `## [Unreleased]` items into a new `## [X.Y.Z] - YYYY-MM-DD`
   section of `CHANGELOG.md`.
3. **Commit on `main`** (`pyproject.toml` + `CHANGELOG.md` + `uv.lock`), then tag and push — the
   workflow validates that the tag matches `pyproject.toml` and fails the release if it does not:
   `git tag vX.Y.Z && git push origin main && git push origin vX.Y.Z`.
4. **Approve the publish**: the final job pauses on the GitHub `pypi` environment for manual
   approval, then publishes via PyPI Trusted Publishing (OIDC — no stored token).
