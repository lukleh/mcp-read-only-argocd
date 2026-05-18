import pytest

from mcp_read_only_argocd.config import ConfigParser
from mcp_read_only_argocd.runtime_paths import resolve_runtime_paths


def test_resolve_runtime_paths_env_overrides(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    cache_dir = tmp_path / "cache"

    monkeypatch.setenv("MCP_READ_ONLY_ARGOCD_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("MCP_READ_ONLY_ARGOCD_STATE_DIR", str(state_dir))
    monkeypatch.setenv("MCP_READ_ONLY_ARGOCD_CACHE_DIR", str(cache_dir))

    runtime_paths = resolve_runtime_paths()

    assert runtime_paths.config_dir == config_dir
    assert runtime_paths.state_dir == state_dir
    assert runtime_paths.cache_dir == cache_dir
    assert runtime_paths.connections_file == config_dir / "connections.yaml"
    assert runtime_paths.state_file == state_dir / "session_tokens.json"


def test_config_parser_reads_yaml_session_token(tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()

    (config_dir / "connections.yaml").write_text(
        "- connection_name: test\n"
        "  url: https://argocd.example.com\n"
        "  session_token: yaml-token\n",
        encoding="utf-8",
    )

    parser = ConfigParser(
        config_dir / "connections.yaml",
        state_path=state_dir / "session_tokens.json",
    )

    [connection] = parser.load_config()

    assert connection.session_token == "yaml-token"


def test_config_parser_reads_state_and_persists_rotated_token(tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()

    (config_dir / "connections.yaml").write_text(
        "- connection_name: test\n"
        "  url: https://argocd.example.com\n"
        "  session_token: yaml-token\n",
        encoding="utf-8",
    )
    (state_dir / "session_tokens.json").write_text(
        '{"test": "state-token"}\n',
        encoding="utf-8",
    )

    parser = ConfigParser(
        config_dir / "connections.yaml",
        state_path=state_dir / "session_tokens.json",
    )

    connections = parser.load_config()

    assert len(connections) == 1
    connection = connections[0]
    assert connection.session_token == "state-token"

    connection.update_session_token("rotated-token", persist=True)

    assert '"test": "rotated-token"' in (state_dir / "session_tokens.json").read_text(
        encoding="utf-8"
    )


def test_state_file_overrides_yaml_session_token(tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()

    (config_dir / "connections.yaml").write_text(
        "- connection_name: test\n"
        "  url: https://argocd.example.com\n"
        "  session_token: yaml-token\n",
        encoding="utf-8",
    )
    (state_dir / "session_tokens.json").write_text(
        '{"test": "state-token"}\n',
        encoding="utf-8",
    )

    parser = ConfigParser(
        config_dir / "connections.yaml",
        state_path=state_dir / "session_tokens.json",
    )

    [connection] = parser.load_config()

    assert connection.session_token == "state-token"


def test_session_environment_variable_is_ignored(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()

    monkeypatch.setenv("ARGOCD_SESSION_TEST", "env-token")
    (config_dir / "connections.yaml").write_text(
        "- connection_name: test\n" "  url: https://argocd.example.com\n",
        encoding="utf-8",
    )

    parser = ConfigParser(
        config_dir / "connections.yaml",
        state_path=state_dir / "session_tokens.json",
    )

    with pytest.raises(ValueError, match="session_token in connections.yaml"):
        parser.load_config()
