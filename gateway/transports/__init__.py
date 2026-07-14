"""Transport factories for the different upstream MCP server kinds."""

from __future__ import annotations

from fastmcp.client.transports import ClientTransport

from ..loader import ServerConfig
from .sse import build_sse_transport
from .stdio import build_stdio_transport
from .streamable_http import build_streamable_http_transport
from .websocket import build_websocket_transport

__all__ = ["build_transport"]

_BUILDERS = {
    "stdio": build_stdio_transport,
    "streamable-http": build_streamable_http_transport,
    "sse": build_sse_transport,
    "websocket": build_websocket_transport,
}


def build_transport(config: ServerConfig) -> ClientTransport:
    """Build the appropriate :class:`ClientTransport` for ``config.type``."""
    try:
        builder = _BUILDERS[config.type]
    except KeyError as exc:
        raise ValueError(f"Unsupported server type: {config.type!r}") from exc
    return builder(config)
