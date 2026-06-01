import pytest

from mcp_read_only_argocd.config import ConfigParser
from mcp_read_only_argocd.runtime_paths import resolve_runtime_paths


def test_resolve_runtime_paths_env_overrides(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache"

    monkeypatch.setenv("MCP_READ_ONLY_ARGOCD_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("MCP_READ_ONLY_ARGOCD_CACHE_DIR", str(cache_dir))

    runtime_paths = resolve_runtime_paths()

    assert runtime_paths.config_dir == config_dir
    assert runtime_paths.cache_dir == cache_dir
    assert runtime_paths.connections_file == config_dir / "connections.yaml"


def test_config_parser_reads_yaml_session_token(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "connections.yaml").write_text(
        "- connection_name: test\n"
        "  url: https://argocd.example.com\n"
        "  session_token: yaml-token\n",
        encoding="utf-8",
    )

    parser = ConfigParser(config_dir / "connections.yaml")

    [connection] = parser.load_config()

    assert connection.session_token == "yaml-token"


def test_connection_persists_rotated_token_to_yaml(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "connections.yaml").write_text(
        "# keep this comment\n"
        "- connection_name: test\n"
        "  url: https://argocd.example.com\n"
        "  session_token: yaml-token\n",
        encoding="utf-8",
    )
    parser = ConfigParser(config_dir / "connections.yaml")

    [connection] = parser.load_config()
    connection.update_session_token("rotated-token", persist=True)

    reloaded_parser = ConfigParser(config_dir / "connections.yaml")
    [reloaded_connection] = reloaded_parser.load_config()
    assert reloaded_connection.session_token == "rotated-token"
    assert "# keep this comment" in (config_dir / "connections.yaml").read_text(
        encoding="utf-8"
    )


def test_session_environment_variable_is_ignored(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    monkeypatch.setenv("ARGOCD_SESSION_TEST", "env-token")
    (config_dir / "connections.yaml").write_text(
        "- connection_name: test\n" "  url: https://argocd.example.com\n",
        encoding="utf-8",
    )

    parser = ConfigParser(config_dir / "connections.yaml")

    with pytest.raises(ValueError, match="session_token in connections.yaml"):
        parser.load_config()
