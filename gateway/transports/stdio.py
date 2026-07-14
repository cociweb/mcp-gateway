"""STDIO transport builder (spawns e.g. ``npx``/``uvx`` subprocesses)."""

from __future__ import annotations

import os

from fastmcp.client.transports import StdioTransport

from ..loader import ServerConfig


def build_stdio_transport(config: ServerConfig) -> StdioTransport:
    if not config.command:
        raise ValueError(f"Server '{config.name}': stdio transport requires 'command'")

    merged_env = {**os.environ, **config.env}

    return StdioTransport(
        command=config.command,
        args=list(config.args),
        env=merged_env,
    )
