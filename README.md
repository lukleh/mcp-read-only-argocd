# MCP Read-Only Argo CD Server

[![Tests](https://github.com/lukleh/mcp-read-only-argocd/actions/workflows/test.yml/badge.svg)](https://github.com/lukleh/mcp-read-only-argocd/actions/workflows/test.yml)

A secure MCP (Model Context Protocol) server that provides **read-only** access to Argo CD instances using browser session cookies.

> Default layout:
> - Config: `~/.config/lukleh/mcp-read-only-argocd/connections.yaml`
> - Credentials: injected via the MCP client or shell environment
> - Rotated session state: `~/.local/state/lukleh/mcp-read-only-argocd/session_tokens.json`

## Features

- **Read-only by design** - Only read operations are exposed; no mutations of Argo CD resources
- **Session cookie authentication** - Uses your browser `argocd.token` cookie (default)
- **Multi‑instance support** - Connect to multiple Argo CD instances simultaneously
- **Automatic cookie rotation** - Captures refreshed `argocd.token` values from response headers while the session is still valid

## Why Session Cookies?

Unlike the official `mcp-for-argocd` which requires generating API tokens, this server can use your existing browser session. This means:

- No need to generate and manage API tokens
- Uses your existing SSO/LDAP/OIDC authentication
- Same permissions as your browser session

## Prerequisites

- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

Alternatively, install editable:

```bash
uv pip install -e .
```

### 2. Configure Argo CD Connections

Create the config and state directories:

```bash
mkdir -p ~/.config/lukleh/mcp-read-only-argocd
mkdir -p ~/.local/state/lukleh/mcp-read-only-argocd
```

Copy the sample configuration:

```bash
cp connections.yaml.sample ~/.config/lukleh/mcp-read-only-argocd/connections.yaml
```

Edit `~/.config/lukleh/mcp-read-only-argocd/connections.yaml` with your Argo CD instances:

```yaml
- connection_name: staging
  url: https://argocd.example.com
  description: Staging Argo CD
```

### 3. Set Up Authentication

Set your browser session cookie in the environment used to launch the server
(for example, export it in your shell for local testing or inject it via your
MCP client config):

```bash
export ARGOCD_SESSION_STAGING=your_session_token_here
```

#### How to Get Your `argocd.token` Session Cookie

1. Log into your Argo CD web UI
2. Open Developer Tools
3. Go to Application/Storage → Cookies
4. Copy the value of the `argocd.token` cookie
5. Export or inject it as `ARGOCD_SESSION_<CONNECTION_NAME>`

The server writes refreshed cookies to `~/.local/state/lukleh/mcp-read-only-argocd/session_tokens.json` automatically. You do not need to create that file yourself.

### 4. Validate and Test Connections

```bash
# Test all configured connections
uv run python smoke_test.py

# Test a specific connection
uv run python smoke_test.py --connection staging

# Show the exact paths the helper will use
uv run python smoke_test.py --print-paths
```

### 5. Run the Server

Run the server manually to verify:

```bash
uv run python -m src.server

# Or if installed as a script:
mcp-read-only-argocd
```

You can also point the server at another config directory:

```bash
uv run python -m src.server --config-dir /path/to/config-dir
```

### 6. Add MCP to Your AI Assistant

For **Claude Code**:
```bash
claude mcp add mcp-read-only-argocd -- uv --directory {PATH_TO_MCP_READ_ONLY_ARGOCD} run python -m src.server
```

For **Codex**:
```bash
codex mcp add mcp-read-only-argocd -- uv --directory {PATH_TO_MCP_READ_ONLY_ARGOCD} run python -m src.server
```

Replace `{PATH_TO_MCP_READ_ONLY_ARGOCD}` with the absolute path where you cloned this repo (e.g., `/Users/yourname/projects/mcp-read-only-argocd`).
Also configure one `ARGOCD_SESSION_<CONNECTION_NAME>` environment variable per
connection in the same MCP entry.

## MCP Tools

### Core
- `list_connections` - List all configured Argo CD connections
- `get_version` - Get Argo CD version information
- `get_settings` - Get Argo CD settings

### Applications
- `list_applications` - List all applications (with optional project/label filters)
- `get_application` - Get application details
- `get_application_resource_tree` - Get Kubernetes resource tree
- `get_application_managed_resources` - Get managed resources
- `get_application_logs` - Get application pod logs

### Projects
- `list_projects` - List all projects
- `get_project` - Get project details

### Clusters
- `list_clusters` - List all registered clusters
- `get_cluster` - Get cluster details

### Repositories
- `list_repositories` - List all configured repositories
- `get_repository` - Get repository details

## Example Queries

Once connected via Claude Code, Codex, or another MCP client:

```
"List all applications in the staging Argo CD"

"Show me the resource tree for the 'my-app' application"

"What clusters are registered in production Argo CD?"

"Get the logs for the 'frontend' application"
```

## License

MIT
