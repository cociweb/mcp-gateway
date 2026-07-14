"""Tests for gateway.loader: env interpolation, parsing, validation."""

from __future__ import annotations

import json

import pytest

from gateway.loader import ConfigError, interpolate_env, load_config


def test_interpolate_env_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOO", "bar")
    assert interpolate_env("value=${FOO}") == "value=bar"


def test_interpolate_env_default_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    assert interpolate_env("${MISSING_VAR:-fallback}") == "fallback"


def test_interpolate_env_default_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    assert interpolate_env("${MISSING_VAR:-}") == ""


def test_interpolate_env_missing_no_default_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISSING_VAR", raising=False)
    with pytest.raises(ConfigError):
        interpolate_env("${MISSING_VAR}")


def test_load_config_missing_file(tmp_path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.json")


def test_load_config_invalid_json(tmp_path) -> None:
    config_file = tmp_path / "mcpServers.json"
    config_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_load_config_missing_top_level_key(tmp_path) -> None:
    config_file = tmp_path / "mcpServers.json"
    config_file.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_load_config_stdio_requires_command(tmp_path) -> None:
    config_file = tmp_path / "mcpServers.json"
    config_file.write_text(
        json.dumps({"mcpServers": {"a": {"type": "stdio", "enabled": True}}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_load_config_disabled_stdio_without_command_ok(tmp_path) -> None:
    config_file = tmp_path / "mcpServers.json"
    config_file.write_text(
        json.dumps({"mcpServers": {"a": {"type": "stdio", "enabled": False}}}),
        encoding="utf-8",
    )
    servers = load_config(config_file)
    assert servers["a"].enabled is False


def test_load_config_http_requires_url(tmp_path) -> None:
    config_file = tmp_path / "mcpServers.json"
    config_file.write_text(
        json.dumps(
            {"mcpServers": {"a": {"type": "streamable-http", "enabled": True}}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_file)


def test_load_config_full_example(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROOT", "/data")
    config_file = tmp_path / "mcpServers.json"
    config_file.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "fs": {
                        "type": "stdio",
                        "enabled": True,
                        "command": "npx",
                        "args": ["-y", "server-fs", "${ROOT}"],
                        "namespace": "files",
                        "readOnly": True,
                        "prefixTools": True,
                        "toolFilter": ["read_*"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    servers = load_config(config_file)
    cfg = servers["fs"]
    assert cfg.args == ["-y", "server-fs", "/data"]
    assert cfg.effective_namespace == "files"
    assert cfg.readOnly is True
    assert cfg.toolFilter == ["read_*"]


def test_load_config_invalid_type(tmp_path) -> None:
    config_file = tmp_path / "mcpServers.json"
    config_file.write_text(
        json.dumps({"mcpServers": {"a": {"type": "bogus", "enabled": True}}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(config_file)
