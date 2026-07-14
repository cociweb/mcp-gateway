"""MCP Gateway entrypoint.

Builds the aggregated FastMCP server from ``config/mcpServers.json`` and
serves it over streamable-HTTP, optionally watching the config file for
changes and restarting the process in-place to pick them up.
"""

from __future__ import annotations

import asyncio
import os
import sys

from .config import GatewayConfig
from .health import register_health_routes
from .loader import ConfigError, load_config
from .logging import get_logger, setup_logging
from .proxy import GatewayState, build_gateway
from .reload import ConfigReloader

logger = get_logger(__name__)


def _restart_process() -> None:
    logger.warning("Restarting gateway process to apply configuration changes...")
    os.execv(sys.executable, [sys.executable, "-m", "gateway.main"])


async def run_gateway() -> None:
    config = GatewayConfig.from_env()
    setup_logging(config.log_level)

    try:
        servers = load_config(config.servers_config_path)
    except ConfigError as exc:
        logger.error("Failed to load gateway configuration: %s", exc)
        sys.exit(1)

    main, state = await build_gateway(
        servers,
        prefix_tools_default=config.prefix_tools,
    )
    state_ref: dict[str, GatewayState] = {"state": state}
    register_health_routes(
        main,
        state_ref,
        health_enabled=config.health_endpoint,
        metrics_enabled=config.metrics,
    )

    reloader: ConfigReloader | None = None
    if config.reload:
        async def on_change() -> None:
            _restart_process()

        reloader = ConfigReloader(config.servers_config_path, on_change)
        reloader.start()

    logger.info(
        "Starting MCP gateway on %s:%d%s (%d server(s) mounted)",
        config.listen,
        config.port,
        config.path,
        state.enabled_count,
    )

    try:
        await main.run_http_async(
            host=config.listen,
            port=config.port,
            path=config.path,
            log_level=config.log_level.lower(),
        )
    finally:
        if reloader is not None:
            reloader.stop()


def cli() -> None:
    asyncio.run(run_gateway())


if __name__ == "__main__":
    cli()
