# Repository Guidelines

## Project Overview

MCP Read-Only Argo CD Server provides read-only access to Argo CD instances via the Model Context Protocol (MCP). It uses browser session cookie authentication and supports multiple Argo CD connections simultaneously.

## Project Structure & Module Organization
`src/mcp_read_only_argocd/server.py` is the MCP entry point and wires the domain tool modules under `src/mcp_read_only_argocd/tools/`. Connection parsing and token resolution live in `config.py`; HTTP calls and cookie rotation live in `argocd_connector.py`; the Chrome cookie fallback lives in `chrome_session.py`; shared error types are in `exceptions.py`; runtime path resolution is in `runtime_paths.py`; and validation helpers are in `validation.py`. Tests live in `tests/`, and `smoke_test.py` is the checkout-level connectivity probe for configured Argo CD instances.

## Build, Test, and Development Commands
- `uv sync --extra dev` installs runtime and development dependencies.
- `uv run python -m mcp_read_only_argocd.server` runs the server manually for testing.
- `uv run mcp-read-only-argocd --print-paths` shows the resolved config, state, and cache locations.
- `uv run mcp-read-only-argocd --write-sample-config` writes the default `connections.yaml`; add `--overwrite` only when you intend to replace it.
- `uv run pytest -q` runs the full test suite.
- `uv run pytest tests/test_server.py -q` runs a focused test module while iterating.
- `uv run python smoke_test.py` exercises every configured connection; add `--connection staging` to scope it to one.
- `uv run ruff check src tests smoke_test.py` runs linting.
- `uv run ty check` runs the type checker on `src/`.

## Architecture

### Core Components

**src/mcp_read_only_argocd/server.py** - MCP server entry point
- `ReadOnlyArgoCDServer` class manages connections and orchestrates tool registration
- Calls domain-specific registration functions from `src/mcp_read_only_argocd/tools/`
- Error handling: every tool carries `@surface_tool_errors` below `@mcp.tool()`, so anticipated
  failures reach the caller with their message (see "Error Handling Pattern")

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

Since mcp 2.1 the SDK reports any exception other than `ToolError` to the caller as the generic
`Error executing tool <name>`. `surface_tool_errors` in `validation.py` re-raises the types in
`ANTICIPATED_TOOL_ERRORS` (`ArgoCDError`, `ValueError`, `OSError`) as `ToolError` so the caller
sees the reason; anything else stays a crash with its traceback in the server log. Stack it below
`@mcp.tool()` on every new tool; `tests/test_tool_error_surfacing.py` fails if one is missing.
`AuthenticationError` is still returned as a JSON payload by `render_tool_result()`.
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
5. **MCP error handling**: Raise the typed errors; `@surface_tool_errors` forwards their message to the caller
6. **NDJSON log parsing**: Argo CD log endpoints return newline-delimited JSON; the connector parses this automatically

## Coding Style & Naming Conventions
Target Python 3.11+ with four-space indentation, explicit type hints, and small focused helpers. Use `snake_case` for modules, functions, tests, and config keys; use `PascalCase` for classes and Pydantic models. Keep tool registration split by domain instead of growing `server.py`, and preserve the current exception-driven error flow rather than returning ad hoc error payloads.

## Testing Guidelines
Pytest uses `unit` and `integration` markers from `pyproject.toml`; prefer unit coverage by default and reserve integration runs for live Argo CD environments. Add or update tests whenever request shaping, runtime path handling, cookie refresh, NDJSON log parsing, MCP tool outputs, or hot reload behavior changes. When touching token reload or persistence behavior, cover both YAML-configured and state-file-driven cases.

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

## Commit & Pull Request Guidelines
Use short imperative commit subjects in the existing style, and keep each commit scoped to one behavior change. Pull requests should summarize the affected Argo CD flows, list the commands you ran, and call out any smoke-test or live-environment validation separately from unit tests.

## Security & Configuration Tips
Do not store Argo CD session tokens in source-controlled files; credentials belong in the local runtime `connections.yaml` or the runtime state file only. Preserve the read-only contract by keeping connector traffic to safe endpoints and by treating configured and rotated cookies as sensitive local state.
