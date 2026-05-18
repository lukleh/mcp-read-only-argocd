import os
import tempfile
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, PrivateAttr, field_validator


def _read_state_file(state_path: Path | None) -> dict[str, str]:
    if state_path is None or not state_path.exists():
        return {}

    raw_data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError(f"State file must contain a JSON object: {state_path}")

    return {
        key: value
        for key, value in raw_data.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _persist_state_value(state_path: Path, key: str, new_value: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)

    current_values = _read_state_file(state_path) if state_path.exists() else {}
    current_values[key] = new_value

    temp_fd, temp_path = tempfile.mkstemp(
        dir=state_path.parent,
        prefix=f".{state_path.name}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            json.dump(current_values, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, state_path)
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

    _state_path: Path | None = PrivateAttr(default=None)
    _configured_session_token: str | None = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        """Preserve the session token explicitly declared in YAML config."""
        self._configured_session_token = self.session_token

    @field_validator("connection_name")
    @classmethod
    def validate_connection_name(cls, value: str) -> str:
        """Ensure connection name is valid for state-file keys."""
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
        state_path: Path | None,
    ) -> None:
        self._state_path = state_path

    def get_state_key(self) -> str:
        """Get the session state key for this connection."""
        return self.connection_name

    def _load_credential_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if self._configured_session_token:
            values[self.get_state_key()] = self._configured_session_token
        values.update(_read_state_file(self._state_path))
        return values

    def reload_session_token(self) -> str:
        """Reload session token from YAML config and cached rotated state."""
        session_token = self._load_credential_values().get(self.get_state_key())

        if not session_token:
            raise ValueError(
                f"Missing session token for connection '{self.connection_name}'. "
                "Please set session_token in connections.yaml."
            )

        self.session_token = session_token
        return session_token

    def update_session_token(self, new_token: str, persist: bool = True) -> None:
        """Update session token in memory and optionally persist to cached state."""
        self.session_token = new_token
        if persist:
            self._persist_token_to_state(new_token)

    def _persist_token_to_state(self, new_token: str) -> None:
        state_path = self._state_path
        if state_path is None:
            return
        _persist_state_value(state_path, self.get_state_key(), new_token)


class ConfigParser:
    """Parser for Argo CD connections configuration."""

    def __init__(
        self,
        config_path: str | Path,
        *,
        state_path: str | Path | None = None,
    ):
        self.config_path = Path(config_path).expanduser()
        self.state_path = Path(state_path).expanduser() if state_path else None

    def load_config(self) -> list[ArgoCDConnection]:
        """Load and parse connection configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        yaml_text = self.config_path.read_text(encoding="utf-8")
        return self.load_config_from_text(yaml_text)

    def load_config_from_text(self, yaml_text: str) -> list[ArgoCDConnection]:
        """Load and parse connection configuration from a YAML text snapshot."""
        raw_config = yaml.safe_load(yaml_text) or []

        return [self._process_connection(conn_data) for conn_data in raw_config]

    def _process_connection(self, conn_data: dict[str, Any]) -> ArgoCDConnection:
        """Process a single connection configuration."""
        connection = ArgoCDConnection(**conn_data)
        connection.configure_credential_sources(
            self.state_path,
        )

        connection.reload_session_token()

        return connection
