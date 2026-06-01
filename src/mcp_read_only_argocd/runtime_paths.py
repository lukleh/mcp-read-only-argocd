from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ORG_NAMESPACE = "lukleh"
APP_NAME = "mcp-read-only-argocd"
ENV_PREFIX = "MCP_READ_ONLY_ARGOCD"


@dataclass(frozen=True)
class RuntimePaths:
    config_dir: Path
    cache_dir: Path

    @property
    def connections_file(self) -> Path:
        return self.config_dir / "connections.yaml"

    def render(self) -> str:
        return "\n".join(
            [
                f"config_dir={self.config_dir}",
                f"cache_dir={self.cache_dir}",
                f"connections_file={self.connections_file}",
            ]
        )

    def ensure_directories(self) -> None:
        for path in (self.config_dir, self.cache_dir):
            path.mkdir(parents=True, exist_ok=True)


def _expand_path(value: str | Path) -> Path:
    return Path(value).expanduser()


def _default_config_dir() -> Path:
    return Path.home() / ".config" / ORG_NAMESPACE / APP_NAME


def _default_cache_dir() -> Path:
    return Path.home() / ".cache" / ORG_NAMESPACE / APP_NAME


def resolve_runtime_paths(
    config_dir: str | Path | None = None,
    cache_dir: str | Path | None = None,
) -> RuntimePaths:
    resolved_config_dir = _expand_path(
        config_dir or os.getenv(f"{ENV_PREFIX}_CONFIG_DIR") or _default_config_dir()
    )
    resolved_cache_dir = _expand_path(
        cache_dir or os.getenv(f"{ENV_PREFIX}_CACHE_DIR") or _default_cache_dir()
    )

    return RuntimePaths(
        config_dir=resolved_config_dir,
        cache_dir=resolved_cache_dir,
    )
