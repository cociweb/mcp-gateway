"""SSE transport builder."""

from __future__ import annotations

from fastmcp.client.transports import SSETransport

from ..loader import ServerConfig


def build_sse_transport(config: ServerConfig) -> SSETransport:
    if not config.url:
        raise ValueError(f"Server '{config.name}': sse transport requires 'url'")

    return SSETransport(
        url=config.url,
        headers=dict(config.headers) or None,
    )
