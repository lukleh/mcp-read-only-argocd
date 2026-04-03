# Repository Guidelines

## Project Structure & Module Organization
`src/mcp_read_only_argocd/server.py` is the MCP entry point and wires the domain tool modules under `src/mcp_read_only_argocd/tools/`. Connection parsing and token resolution live in `config.py`; HTTP calls and cookie rotation live in `argocd_connector.py`; shared error types are in `exceptions.py`; runtime path resolution is in `runtime_paths.py`; and validation helpers are in `validation.py`. Tests live in `tests/`, and `smoke_test.py` is the checkout-level connectivity probe for configured Argo CD instances.

## Build, Test, and Development Commands
- `uv sync --extra dev` installs runtime and development dependencies.
- `uv run mcp-read-only-argocd --print-paths` shows the resolved config, state, and cache locations.
- `uv run mcp-read-only-argocd --write-sample-config` writes the default `connections.yaml`; add `--overwrite` only when you intend to replace it.
- `uv run pytest -q` runs the full test suite.
- `uv run pytest tests/test_server.py -q` runs a focused test module while iterating.
- `uv run python smoke_test.py --connection staging` exercises one configured connection end to end.
- `uv run ruff check src tests smoke_test.py` runs linting, and `uv run black src tests smoke_test.py` formats the repo.
- `uv run ty check` runs the type checker on `src/`.

## Coding Style & Naming Conventions
Target Python 3.11+ with four-space indentation, explicit type hints, and small focused helpers. Use `snake_case` for modules, functions, tests, and config keys; use `PascalCase` for classes and Pydantic models. Keep tool registration split by domain instead of growing `server.py`, and preserve the current exception-driven error flow rather than returning ad hoc error payloads.

## Testing Guidelines
Pytest uses `unit` and `integration` markers from `pyproject.toml`; prefer unit coverage by default and reserve integration runs for live Argo CD environments. Add or update tests whenever request shaping, runtime path handling, cookie refresh, NDJSON log parsing, or MCP tool outputs change. When touching token reload or persistence behavior, cover both environment-driven and state-file-driven cases.

## Commit & Pull Request Guidelines
Use short imperative commit subjects in the existing style, and keep each commit scoped to one behavior change. Pull requests should summarize the affected Argo CD flows, list the commands you ran, and call out any smoke-test or live-environment validation separately from unit tests.

## Security & Configuration Tips
Do not store Argo CD session tokens in source-controlled files; credentials belong in `ARGOCD_SESSION_<CONNECTION_NAME>` or the runtime state file only. Preserve the read-only contract by keeping connector traffic to safe endpoints and by treating rotated cookies as sensitive state under `~/.local/state/lukleh/mcp-read-only-argocd/`.
