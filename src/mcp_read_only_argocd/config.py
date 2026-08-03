import os
import tempfile
from collections.abc import MutableMapping, MutableSequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, PrivateAttr, field_validator
from ruamel.yaml import YAML as RoundTripYAML


def _persist_yaml_session_token(
    config_path: Path,
    connection_name: str,
    new_token: str,
) -> None:
    """Atomically update one connection's session_token in connections.yaml."""
    yaml_writer = RoundTripYAML()
    yaml_writer.preserve_quotes = True
    raw_config = yaml_writer.load(config_path.read_text(encoding="utf-8")) or []
    if not isinstance(raw_config, MutableSequence):
        raise ValueError(f"Configuration file must contain a list: {config_path}")

    updated = False
    for connection in raw_config:
        if not isinstance(connection, MutableMapping):
            continue
        if connection.get("connection_name") != connection_name:
            continue
        connection["session_token"] = new_token
        updated = True
        break

    if not updated:
        raise ValueError(
            f"Connection '{connection_name}' not found in configuration file: {config_path}"
        )

    temp_fd, temp_path = tempfile.mkstemp(
        dir=config_path.parent,
        prefix=f".{config_path.name}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            yaml_writer.dump(raw_config, handle)
        os.replace(temp_path, config_path)
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

    _config_path: Path | None = PrivateAttr(default=None)
    _configured_session_token: str | None = PrivateAttr(default=None)

    # pydantic's documented hook signature uses a dunder-named parameter
    def model_post_init(self, __context: Any) -> None:  # noqa: PYI063
        """Preserve the session token explicitly declared in YAML config."""
        self._configured_session_token = self.session_token

    @field_validator("connection_name")
    @classmethod
    def validate_connection_name(cls, value: str) -> str:
        """Ensure connection name is valid for tool calls and YAML persistence."""
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
        config_path: Path | None,
    ) -> None:
        self._config_path = config_path

    def reload_session_token(self) -> str:
        """Reload session token from the loaded YAML configuration."""
        session_token = self._configured_session_token

        if not session_token:
            raise ValueError(
                f"Missing session token for connection '{self.connection_name}'. "
                "Please set session_token in connections.yaml."
            )

        self.session_token = session_token
        return session_token

    def update_session_token(self, new_token: str, persist: bool = True) -> None:
        """Update session token in memory and optionally persist to connections.yaml."""
        self.session_token = new_token
        if persist:
            self._configured_session_token = new_token
            self._persist_token_to_yaml(new_token)

    def _persist_token_to_yaml(self, new_token: str) -> None:
        config_path = self._config_path
        if config_path is None:
            return
        _persist_yaml_session_token(config_path, self.connection_name, new_token)


class ConfigParser:
    """Parser for Argo CD connections configuration."""

    def __init__(
        self,
        config_path: str | Path,
    ):
        self.config_path = Path(config_path).expanduser()

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
            self.config_path,
        )

        connection.reload_session_token()

        return connection
