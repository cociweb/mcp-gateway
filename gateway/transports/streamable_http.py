"""Streamable-HTTP transport builder."""

from __future__ import annotations

from fastmcp.client.transports import StreamableHttpTransport

from ..loader import ServerConfig


def build_streamable_http_transport(config: ServerConfig) -> StreamableHttpTransport:
    if not config.url:
        raise ValueError(
            f"Server '{config.name}': streamable-http transport requires 'url'"
        )

    return StreamableHttpTransport(
        url=config.url,
        headers=dict(config.headers) or None,
    )
