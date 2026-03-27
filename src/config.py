import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field, HttpUrl, PrivateAttr, field_validator


def _read_env_file(env_path: Path | None) -> dict[str, str]:
    if env_path is None or not env_path.exists():
        return {}
    return {
        key: value
        for key, value in dotenv_values(env_path).items()
        if key and value is not None
    }


def _merge_credential_sources(
    secrets_path: Path | None,
    state_path: Path | None,
    runtime_env: Mapping[str, str] | None,
) -> dict[str, str]:
    merged = _read_env_file(secrets_path)
    merged.update(_read_env_file(state_path))
    if runtime_env:
        merged.update(runtime_env)
    return merged


def _persist_env_value(env_path: Path, env_var_name: str, new_value: str) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)

    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    updated = False
    for index, line in enumerate(lines):
        if line.startswith(f"{env_var_name}="):
            lines[index] = f"{env_var_name}={new_value}"
            updated = True
            break

    if not updated:
        lines.append(f"{env_var_name}={new_value}")

    temp_fd, temp_path = tempfile.mkstemp(
        dir=env_path.parent,
        prefix=f".{env_path.name}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        os.replace(temp_path, env_path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


class ArgoCDConnection(BaseModel):
    """Configuration for a single Argo CD connection."""

    connection_name: str = Field(
        ..., description="Unique identifier for this connection"
    )
    url: HttpUrl = Field(..., description="Argo CD instance URL")
    description: str = Field("", description="Description of this Argo CD instance")
    timeout: int = Field(30, description="Request timeout in seconds")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")
    session_token: str | None = Field(
        None, description="Argo CD session token (argocd.token cookie)"
    )

    _secrets_path: Path | None = PrivateAttr(default=None)
    _state_path: Path | None = PrivateAttr(default=None)
    _runtime_env_provider: Callable[[], Mapping[str, str]] = PrivateAttr(
        default=os.environ.copy
    )

    @field_validator("connection_name")
    @classmethod
    def validate_connection_name(cls, value: str) -> str:
        """Ensure connection name is valid for environment variable naming."""
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Connection name must contain only letters, numbers, underscores, and hyphens"
            )
        return value

    @field_validator("url")
    @classmethod
    def remove_trailing_slash(cls, value: HttpUrl) -> str:
        """Remove trailing slash from URL if present."""
        return str(value).rstrip("/")

    def configure_credential_sources(
        self,
        secrets_path: Path | None,
        state_path: Path | None,
        runtime_env_provider: Callable[[], Mapping[str, str]] | None = None,
    ) -> None:
        self._secrets_path = secrets_path
        self._state_path = state_path
        if runtime_env_provider is not None:
            self._runtime_env_provider = runtime_env_provider

    def get_env_var_name(self) -> str:
        """Get the environment variable name for this connection's session token."""
        return f"ARGOCD_SESSION_{self.connection_name.upper().replace('-', '_')}"

    def get_timeout_env_var_name(self) -> str:
        return f"ARGOCD_TIMEOUT_{self.connection_name.upper().replace('-', '_')}"

    def _load_credential_values(self) -> dict[str, str]:
        return _merge_credential_sources(
            self._secrets_path,
            self._state_path,
            self._runtime_env_provider(),
        )

    def reload_session_token(self) -> str:
        """Reload session token from secrets/state files and runtime environment."""
        env_var_name = self.get_env_var_name()
        session_token = self._load_credential_values().get(env_var_name)

        if not session_token:
            raise ValueError(
                f"Missing session token for connection '{self.connection_name}'. "
                f"Please set {env_var_name} in secrets.env, state.env, or the environment."
            )

        self.session_token = session_token
        return session_token

    def update_session_token(self, new_token: str, persist: bool = True) -> None:
        """Update session token in memory and optionally persist to state.env."""
        self.session_token = new_token
        if persist:
            self._persist_token_to_state(new_token)

    def _persist_token_to_state(self, new_token: str) -> None:
        env_path = self._state_path
        if env_path is None:
            return
        _persist_env_value(env_path, self.get_env_var_name(), new_token)


class ConfigParser:
    """Parser for Argo CD connections configuration."""

    def __init__(
        self,
        config_path: str | Path,
        *,
        secrets_path: str | Path | None = None,
        state_path: str | Path | None = None,
        runtime_env_provider: Callable[[], Mapping[str, str]] | None = None,
    ):
        self.config_path = Path(config_path).expanduser()
        self.secrets_path = Path(secrets_path).expanduser() if secrets_path else None
        self.state_path = Path(state_path).expanduser() if state_path else None
        self.runtime_env_provider = runtime_env_provider or os.environ.copy

    def load_config(self) -> list[ArgoCDConnection]:
        """Load and parse connection configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with self.config_path.open("r", encoding="utf-8") as handle:
            raw_config = yaml.safe_load(handle) or []

        return [self._process_connection(conn_data) for conn_data in raw_config]

    def _process_connection(self, conn_data: dict[str, Any]) -> ArgoCDConnection:
        """Process a single connection configuration."""
        connection = ArgoCDConnection(**conn_data)
        connection.configure_credential_sources(
            self.secrets_path,
            self.state_path,
            self.runtime_env_provider,
        )

        env_values = connection._load_credential_values()
        session_token = env_values.get(connection.get_env_var_name())
        if session_token:
            connection.session_token = session_token

        if not session_token:
            raise ValueError(
                f"Missing session token for connection '{connection.connection_name}'. "
                f"Please set {connection.get_env_var_name()} in secrets.env, state.env, or the environment."
            )

        timeout_override = env_values.get(connection.get_timeout_env_var_name())
        if timeout_override:
            try:
                connection.timeout = int(timeout_override)
            except ValueError:
                pass

        return connection
