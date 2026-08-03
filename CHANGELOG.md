# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Dev tooling: adopted ruff 0.16's widened default rule set, with ruff capped
  to the 0.16 minor (`ruff>=0.16,<0.17`) so relocks cannot change lint
  behavior silently. `BLE001` and `TRY004` are deliberately ignored (broad
  excepts at MCP tool boundaries and raised exception types are API design,
  not lint debt). Code modernized accordingly: PEP 585/604 annotations,
  sorted imports, and other mechanical autofixes; no behavior changes. Also
  removed the `black` dev dependency (it was enforced by no CI step or
  release gate).

## [0.4.0] - 2026-08-03

### Changed

- Ported the server to MCP Python SDK 2.x: `mcp.server.fastmcp.FastMCP` is now
  `mcp.server.mcpserver.MCPServer`, and `mcp.server.fastmcp.exceptions.ToolError`
  is now `mcp.server.mcpserver.exceptions.ToolError`. `mcp.server.mcpserver`
  mirrors the removed `fastmcp` package, so the tool registration API
  (`@mcp.tool()`, type-hint-derived schemas) and the `run()` entry point are
  unchanged. Not everything moved cleanly, though: `ToolManager.call_tool()`
  now takes the request `Context` as a required positional argument (it was
  optional in 1.x), so the shared test helper in `tests/test_connections_reload.py`
  builds one the same way `MCPServer.call_tool` does
  (`Context(mcp_server=..., subscriptions=...)`). That change is test-only;
  tool behaviour and assertions are unchanged.
  The 14 tools' `tools/list` output — names, descriptions, input schemas and
  output schemas — is byte-identical to the 0.3.1 output.
- Replaced the `mcp>=1.10.0,<2` pin with `mcp>=2.0.0,<3`. The cap is kept
  because 2.0.0 removed `mcp.server.fastmcp` with no compatibility shim, so an
  unbounded pin lets the next major SDK rewrite break fresh installs the same
  way. SDK 2.0.0 requires Python >=3.10; this package already requires >=3.11,
  so the supported Python range is unaffected.
- `serverInfo.version` in the `initialize` response now reports this package's
  version (`0.4.0`) instead of the MCP SDK's version. Under FastMCP the field
  was populated from the SDK release (0.3.1 advertised `1.29.0`); SDK 2 defaults
  it to an empty string, and the server now passes its own version explicitly.

## [0.3.1] - 2026-08-03

### Fixed

- Constrained the MCP Python SDK dependency to `mcp>=1.10.0,<2`. The SDK's 2.0.0 release (2026-07-28) removed `mcp.server.fastmcp`, which this server imports, so any fresh install resolving to 2.x crashed on startup with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` and the server never connected. The previous floor of `>=1.0.0` was also wrong in the other direction: `mcp.server.fastmcp` only appeared in 1.2.0, and FastMCP only emits `outputSchema` / structured content from 1.10.0, so older 1.x resolves either crashed identically or started with the tools' declared output schemas silently missing. The committed `uv.lock` pinned the SDK at 1.27.0, so `uv sync` and local development were unaffected; the break reached only installs that resolve fresh from PyPI. CI would have caught it — the `package-smoke` job builds the wheel and resolves it from the index, bypassing the lock — but no run happened on `main` between the SDK 2.0.0 release and this change. The cap stays until the server is ported to the 2.x API.

## [0.3.0] - 2026-06-01

### Added

- Refresh stale Argo CD `argocd.token` cookies from Chrome Profile 1 after a
  401 response, retry once, and save a working token back to
  `connections.yaml`.
- Return structured JSON authentication failures from MCP tools when both the
  configured token and Chrome token cannot authenticate.

### Changed

- Treat `connections.yaml` as the only token store and write refreshed tokens
  back to it with comment-preserving YAML updates.
- Remove the `session_tokens.json` state file and `--state-dir` CLI option.
- Update packaged artifact smoke tests for the single-YAML runtime layout.

## [0.2.0] - 2026-05-18

### Changed

- Store Argo CD `argocd.token` session cookies in runtime `connections.yaml`
  instead of `ARGOCD_SESSION_<CONNECTION_NAME>` environment variables.
- Store rotated session cookies in `session_tokens.json` keyed by
  `connection_name` instead of env-var-style names.
- Hot-reload `connections.yaml` before tool calls so token and connection
  edits do not require restarting the MCP server.
- Remove per-connection session and timeout environment variable support.

## [0.1.2] - 2026-04-03

### Added

- Root `CHANGELOG.md` using the Keep a Changelog format and seeded package history.
- Added `ty` as a supported development check for the packaged `src/` tree.
- Added a repo-specific `AGENTS.md` contributor guide covering layout, commands, and security expectations.

### Changed

- `project.urls.Changelog` now points to the in-repo changelog instead of the generic GitHub releases page.
- The release flow now treats changelog maintenance as a required step and reuses changelog sections for GitHub release notes.
- Reworked `RELEASING.md` into an evergreen release checklist with explicit validation, tagging, and publish steps.

## [0.1.0] - 2026-03-29

### Added

- Initial PyPI release for `uvx mcp-read-only-argocd`.
- Canonical `src/mcp_read_only_argocd` package layout and metadata-backed `__version__`.
- Package-native bootstrap commands for `--write-sample-config`, `--overwrite`, and `--print-paths`.
- Trusted PyPI publishing with a gated GitHub Actions release workflow and manual `pypi` approval.

### Changed

- Standardized the publish workflow around full test gating and packaged artifact smoke tests.
