"""WebSocket transport builder.

FastMCP does not ship a built-in WebSocket ``ClientTransport``, so this module
implements one on top of the low-level ``mcp`` SDK's
``mcp.client.websocket.websocket_client``.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Unpack

from fastmcp.client.transports import ClientTransport, SessionKwargs
from mcp import ClientSession
from mcp.client.websocket import websocket_client

from ..loader import ServerConfig


class WebSocketTransport(ClientTransport):
    """Connects to an MCP server over a plain WebSocket connection."""

    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        if not url.startswith(("ws://", "wss://")):
            raise ValueError(f"Invalid WebSocket URL: {url!r}")
        self.url = url
        self.headers = headers or {}

    @contextlib.asynccontextmanager
    async def connect_session(
        self, **session_kwargs: Unpack[SessionKwargs]
    ) -> AsyncIterator[ClientSession]:
        async with websocket_client(self.url) as (read_stream, write_stream):
            async with ClientSession(
                read_stream, write_stream, **session_kwargs
            ) as session:
                yield session

    def __repr__(self) -> str:
        return f"<WebSocketTransport(url='{self.url}')>"


def build_websocket_transport(config: ServerConfig) -> WebSocketTransport:
    if not config.url:
        raise ValueError(f"Server '{config.name}': websocket transport requires 'url'")

    return WebSocketTransport(url=config.url, headers=dict(config.headers) or None)
