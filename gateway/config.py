"""Gateway-level configuration loaded from environment variables.

Environment variables (all prefixed with ``GATEWAY_`` except
``MCP_SERVERS_CONFIG``) can be set via a ``.env`` file and/or the
``environment:`` section of ``docker-compose.yml``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _str_to_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class GatewayConfig:
    listen: str = "0.0.0.0"
    port: int = 5555
    path: str = "/mcp"
    reload: bool = True
    health_endpoint: bool = True
    metrics: bool = True
    log_level: str = "info"
    prefix_tools: bool = True
    servers_config_path: str = "/app/config/mcpServers.json"

    @classmethod
    def from_env(cls, env_file: str | None = ".env") -> "GatewayConfig":
        if env_file:
            load_dotenv(dotenv_path=env_file, override=False)

        return cls(
            listen=os.environ.get("GATEWAY_LISTEN", "0.0.0.0"),
            port=int(os.environ.get("GATEWAY_PORT", "5555")),
            path=os.environ.get("GATEWAY_PATH", "/mcp"),
            reload=_str_to_bool(os.environ.get("GATEWAY_RELOAD", "true")),
            health_endpoint=_str_to_bool(
                os.environ.get("GATEWAY_HEALTH_ENDPOINT", "true")
            ),
            metrics=_str_to_bool(os.environ.get("GATEWAY_METRICS", "true")),
            log_level=os.environ.get("GATEWAY_LOG_LEVEL", "info"),
            prefix_tools=_str_to_bool(
                os.environ.get("GATEWAY_PREFIX_TOOLS", "true")
            ),
            servers_config_path=os.environ.get(
                "MCP_SERVERS_CONFIG", "/app/config/mcpServers.json"
            ),
        )
