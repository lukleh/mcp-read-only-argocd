# Releasing `mcp-read-only-argocd`

This project is set up for tag-driven PyPI releases with GitHub Actions and PyPI trusted publishing.

## One-time PyPI setup

1. Create the `mcp-read-only-argocd` project on PyPI if it does not exist yet.
2. In PyPI, add a trusted publisher for this repository:
   - Owner: `lukleh`
   - Repository: `mcp-read-only-argocd`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. In GitHub, create an environment named `pypi`.
4. Add required reviewers to the `pypi` environment if you want a manual approval gate before publishing.

## Release steps

1. Update `version` in `pyproject.toml`.
2. Commit the release changes to `main`.
3. Create and push a matching version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

4. GitHub Actions will start the `Publish` workflow and pause at the `pypi` environment for approval.
5. Approve the deployment in the GitHub Actions UI.
6. After approval, GitHub Actions will:
   - run tests
   - build the wheel and sdist
   - smoke test both artifacts with `uvx`
   - publish to PyPI

## Notes

- The publish workflow validates that the Git tag matches `pyproject.toml`.
- The smoke tests exercise the packaged CLI by writing a sample config and printing runtime paths from the built artifacts.
