# Releasing `mcp-read-only-argocd`

This repository publishes to PyPI from Git tags through GitHub Actions.

Release automation lives in:
- `.github/workflows/publish.yml`
- `.github/workflows/test.yml`
- the GitHub environment named `pypi`
- the PyPI trusted publisher for `lukleh/mcp-read-only-argocd`

## What To Change For A Release

Update these files in the release commit:

1. `CHANGELOG.md`
   Move the user-visible items from `## [Unreleased]` into a new section:
   `## [X.Y.Z] - YYYY-MM-DD`
2. `pyproject.toml`
   Update `[project].version` to `X.Y.Z`
3. `uv.lock`
   Refresh the tracked lockfile so the root package entry for
   `mcp-read-only-argocd` matches `pyproject.toml`

`RELEASING.md` should stay evergreen. It should explain the process, not carry a
release-specific version number.

## How To Update The Version

1. Edit `pyproject.toml`
2. Refresh the lockfile:

```bash
uv sync --extra dev
```

3. Confirm the installed package metadata matches the new version:

```bash
uv run --extra dev pytest tests/test_server.py -q -k package_version_matches_distribution_metadata
```

## Pre-Release Validation

Run the normal local checks before tagging:

```bash
uv run --extra dev ruff check src tests smoke_test.py
uv run --extra dev ty check
uv run --extra dev pytest -q
```

Optional manual live check when you have credentials configured:

```bash
uv run python smoke_test.py --print-paths
uv run python smoke_test.py --connection staging
```

## How To Publish

1. Make the release commit on `main`
2. Create and push the matching tag:

```bash
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

3. GitHub Actions starts `.github/workflows/publish.yml`
4. The workflow runs the test matrix, builds the wheel and sdist, and smoke-tests the built artifacts
5. The final publish job pauses on the GitHub `pypi` environment
6. Approve the deployment in GitHub Actions
7. GitHub publishes the package to PyPI

## Notes

- The publish workflow validates that the Git tag matches `pyproject.toml`
- Do not store Argo CD session tokens in release commits or sample configs
- If the public CLI changes, keep the packaged smoke tests and docs aligned with `mcp-read-only-argocd`
