"""Loads and validates ``mcpServers.json`` with environment interpolation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)

_VALID_TYPES = {"stdio", "streamable-http", "sse", "websocket"}

# Matches ${VAR} or ${VAR:-default}
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:-([^}]*))?\}")


class ConfigError(ValueError):
    """Raised for invalid or unresolvable gateway/server configuration."""


def interpolate_env(value: str) -> str:
    """Replace ``${VAR}`` / ``${VAR:-default}`` occurrences in ``value``.

    Raises:
        ConfigError: if a referenced variable has no value and no default.
    """

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        has_default = match.group(2) is not None
        default = match.group(3)
        if var_name in os.environ:
            return os.environ[var_name]
        if has_default:
            return default or ""
        raise ConfigError(
            f"Environment variable '{var_name}' is not set and has no default "
            f"(referenced as '{match.group(0)}')"
        )

    return _ENV_VAR_RE.sub(_replace, value)


def _interpolate_any(value: Any) -> Any:
    if isinstance(value, str):
        return interpolate_env(value)
    if isinstance(value, dict):
        return {k: _interpolate_any(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_any(v) for v in value]
    return value


@dataclass
class ServerConfig:
    name: str
    type: str
    enabled: bool = True
    url: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    namespace: str | None = None
    readOnly: bool = False
    prefixTools: bool | None = None
    toolFilter: list[str] = field(default_factory=lambda: ["*"])
    resourceFilter: list[str] = field(default_factory=lambda: ["*"])
    promptFilter: list[str] = field(default_factory=lambda: ["*"])
    timeout: float = 30.0

    @property
    def effective_namespace(self) -> str:
        return self.namespace or self.name


def _parse_server(name: str, raw: dict[str, Any]) -> ServerConfig:
    enabled = bool(raw.get("enabled", True))
    try:
        raw = _interpolate_any(raw)
    except ConfigError as exc:
        if enabled:
            raise
        logger.warning(
            "Server '%s' is disabled and has unresolved variables (%s); "
            "skipping interpolation",
            name,
            exc,
        )

    server_type = raw.get("type")
    if server_type not in _VALID_TYPES:
        raise ConfigError(
            f"Server '{name}': invalid or missing 'type' "
            f"(must be one of {sorted(_VALID_TYPES)}, got {server_type!r})"
        )

    cfg = ServerConfig(
        name=name,
        type=server_type,
        enabled=bool(raw.get("enabled", True)),
        url=raw.get("url"),
        command=raw.get("command"),
        args=list(raw.get("args", [])),
        env=dict(raw.get("env", {})),
        headers=dict(raw.get("headers", {})),
        namespace=raw.get("namespace"),
        readOnly=bool(raw.get("readOnly", False)),
        prefixTools=raw.get("prefixTools"),
        toolFilter=list(raw.get("toolFilter", ["*"])),
        resourceFilter=list(raw.get("resourceFilter", ["*"])),
        promptFilter=list(raw.get("promptFilter", ["*"])),
        timeout=float(raw.get("timeout", 30.0)),
    )

    if cfg.enabled:
        if server_type == "stdio" and not cfg.command:
            raise ConfigError(f"Server '{name}': stdio type requires 'command'")
        if server_type in ("streamable-http", "sse", "websocket") and not cfg.url:
            raise ConfigError(f"Server '{name}': '{server_type}' type requires 'url'")

    return cfg


def load_config(path: str | Path) -> dict[str, ServerConfig]:
    """Load, interpolate and validate ``mcpServers.json``.

    Returns:
        Mapping of server name -> :class:`ServerConfig`.

    Raises:
        ConfigError: on missing file, invalid JSON, or validation failure.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ConfigError(f"MCP servers config file not found: {file_path}")

    try:
        raw_text = file_path.read_text(encoding="utf-8")
        raw_data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {file_path}: {exc}") from exc

    servers_raw = raw_data.get("mcpServers")
    if not isinstance(servers_raw, dict):
        raise ConfigError(f"{file_path}: missing top-level 'mcpServers' object")

    servers: dict[str, ServerConfig] = {}
    for name, raw in servers_raw.items():
        if not isinstance(raw, dict):
            raise ConfigError(f"Server '{name}': definition must be an object")
        servers[name] = _parse_server(name, raw)

    logger.info(
        "Loaded %d server definitions (%d enabled) from %s",
        len(servers),
        sum(1 for s in servers.values() if s.enabled),
        file_path,
    )
    return servers
