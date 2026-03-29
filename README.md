# MCP Read-Only Argo CD Server

[![Tests](https://github.com/lukleh/mcp-read-only-argocd/actions/workflows/test.yml/badge.svg)](https://github.com/lukleh/mcp-read-only-argocd/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A secure MCP (Model Context Protocol) server that provides read-only access to Argo CD instances using browser session cookies.

> Default layout:
> - Config: `~/.config/lukleh/mcp-read-only-argocd/connections.yaml`
> - Credentials: injected via the MCP client or shell environment
> - State: `~/.local/state/lukleh/mcp-read-only-argocd/session_tokens.json`
> - Cache: `~/.cache/lukleh/mcp-read-only-argocd/`

## Features

- Read-only by design: only read operations are exposed
- Session cookie authentication: uses your existing `argocd.token` browser session
- Multi-instance support: connect to multiple Argo CD instances at once
- Automatic cookie rotation: refreshed session cookies are persisted to local state
- Package-native runtime paths: no repository checkout required for normal use

## Why Session Cookies?

Unlike token-based setups, this server can reuse your existing browser session:

- no extra API token management
- uses your existing SSO/OIDC login
- matches the permissions you already have in the UI

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv)
- an Argo CD browser session cookie
- an MCP client such as Claude Code or Codex

## Quick Start

### 1. Install the Server

```bash
# Run the published package without cloning the repository
uvx mcp-read-only-argocd --write-sample-config

# Or install it once and reuse the command directly
uv tool install mcp-read-only-argocd
mcp-read-only-argocd --write-sample-config
```

The command above writes a starter config to `~/.config/lukleh/mcp-read-only-argocd/connections.yaml`.

### 2. Confirm Runtime Paths

```bash
uvx mcp-read-only-argocd --print-paths
```

### 3. Edit the Connections File

Edit `~/.config/lukleh/mcp-read-only-argocd/connections.yaml`:

```yaml
- connection_name: staging
  url: https://argocd.example.com
  description: Staging Argo CD

- connection_name: production
  url: https://argocd-prod.example.com
  description: Production Argo CD
```

### 4. Get Your `argocd.token` Session Cookie

1. Log in to your Argo CD web UI
2. Open browser developer tools
3. Go to Application/Storage -> Cookies
4. Copy the value of the `argocd.token` cookie

### 5. Set the Environment Variables

Set one `ARGOCD_SESSION_<CONNECTION_NAME>` variable for each configured connection in the environment used to launch the server.

Example:

```bash
export ARGOCD_SESSION_STAGING=your-session-token
export ARGOCD_SESSION_PRODUCTION=your-other-session-token
```

Optional per-connection timeout override:

```bash
export ARGOCD_TIMEOUT_STAGING=60
```

The server persists rotated session cookies to `~/.local/state/lukleh/mcp-read-only-argocd/session_tokens.json`. If both the environment and the state file contain a token, the persisted state file wins until you update or remove it.

### 6. Configure Your MCP Client

**Claude Code**

```bash
claude mcp add mcp-read-only-argocd \
  --scope user \
  -e ARGOCD_SESSION_STAGING=your-session-token \
  -e ARGOCD_SESSION_PRODUCTION=your-other-session-token \
  -- uvx mcp-read-only-argocd
```

**Codex**

```bash
codex mcp add mcp-read-only-argocd \
  --env ARGOCD_SESSION_STAGING=your-session-token \
  --env ARGOCD_SESSION_PRODUCTION=your-other-session-token \
  -- uvx mcp-read-only-argocd
```

### 7. Restart and Test

Restart your MCP client and try a simple query such as:

```text
List all applications in the staging Argo CD instance.
```

## Configuration

`connections.yaml` supports a list of Argo CD connections:

```yaml
- connection_name: staging
  url: https://argocd.example.com
  description: Staging Argo CD instance
  timeout: 30
  verify_ssl: true
```

Fields:

- `connection_name`: unique identifier used to derive environment variable names
- `url`: Argo CD base URL
- `description`: optional human-readable description
- `timeout`: optional request timeout in seconds
- `verify_ssl`: optional SSL verification toggle

Environment variables:

- `ARGOCD_SESSION_<CONNECTION_NAME>`
- `ARGOCD_TIMEOUT_<CONNECTION_NAME>` (optional)
- `MCP_READ_ONLY_ARGOCD_CONFIG_DIR`
- `MCP_READ_ONLY_ARGOCD_STATE_DIR`
- `MCP_READ_ONLY_ARGOCD_CACHE_DIR`

## Command Line Testing

```bash
# Show the resolved runtime paths
uvx mcp-read-only-argocd --print-paths

# Write or refresh the default connections.yaml
uvx mcp-read-only-argocd --write-sample-config
uvx mcp-read-only-argocd --write-sample-config --overwrite

# Run the server with the default home-directory config
uvx mcp-read-only-argocd

# Or point at a different runtime root
uvx mcp-read-only-argocd --config-dir /path/to/config-dir
```

## MCP Tools

### Core

- `list_connections`
- `get_version`
- `get_settings`

### Applications

- `list_applications`
- `get_application`
- `get_application_resource_tree`
- `get_application_managed_resources`
- `get_application_logs`

### Projects

- `list_projects`
- `get_project`

### Clusters

- `list_clusters`
- `get_cluster`

### Repositories

- `list_repositories`
- `get_repository`

## Local Development

If you want to work on the repository itself:

```bash
git clone https://github.com/lukleh/mcp-read-only-argocd.git
cd mcp-read-only-argocd
uv sync --extra dev
uv run pytest -q
uv run mcp-read-only-argocd --print-paths
uv run python smoke_test.py --print-paths
```

The checked-in sample file remains available at [connections.yaml.sample](connections.yaml.sample) for documentation and review, but package users should prefer `--write-sample-config`.

## License

MIT
