"""Builds the aggregated gateway FastMCP server from ``mcpServers.json``.

For every enabled upstream server, a :class:`fastmcp.FastMCP` proxy
sub-server is created (via ``FastMCP.as_proxy``) with a per-server
:class:`~gateway.namespace.ServerFilterMiddleware` attached, then mounted
onto the main gateway server with ``namespace=<effective_namespace>`` when
``prefixTools`` is enabled (or without a namespace otherwise).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastmcp import Client, FastMCP
from fastmcp.server import create_proxy

from .loader import ServerConfig
from .logging import get_logger
from .namespace import build_filter_middleware
from .reconnect import retry_with_backoff
from .transports import build_transport

logger = get_logger(__name__)


@dataclass
class MountedServer:
    config: ServerConfig
    sub_server: FastMCP
    connected: bool = False


@dataclass
class GatewayState:
    """Holds the currently active mounted-server set for health/metrics."""

    mounted: dict[str, MountedServer] = field(default_factory=dict)

    @property
    def enabled_count(self) -> int:
        return len(self.mounted)

    @property
    def connected_count(self) -> int:
        return sum(1 for m in self.mounted.values() if m.connected)


async def _probe_server(config: ServerConfig) -> bool:
    """Best-effort connectivity probe used only for health reporting."""

    async def _attempt() -> bool:
        transport = build_transport(config)
        async with Client(transport, timeout=config.timeout) as client:
            await client.ping()
        return True

    result = await retry_with_backoff(
        _attempt, retries=1, label=f"probe '{config.name}'"
    )
    return bool(result)


async def build_gateway(
    servers: dict[str, ServerConfig],
    *,
    name: str = "MCP Gateway",
    prefix_tools_default: bool = True,
    probe: bool = True,
) -> tuple[FastMCP, GatewayState]:
    """Build a fresh main :class:`FastMCP` server with all enabled servers mounted."""
    main = FastMCP(name=name)
    state = GatewayState()

    for server_name, config in servers.items():
        if not config.enabled:
            logger.info("Skipping disabled server '%s'", server_name)
            continue

        try:
            transport = build_transport(config)
        except ValueError as exc:
            logger.error("Skipping server '%s': %s", server_name, exc)
            continue

        sub = create_proxy(transport, name=server_name)
        sub.add_middleware(build_filter_middleware(config))

        use_prefix = config.prefixTools if config.prefixTools is not None else prefix_tools_default
        namespace = config.effective_namespace if use_prefix else None

        main.mount(sub, namespace=namespace)

        connected = await _probe_server(config) if probe else False
        state.mounted[server_name] = MountedServer(
            config=config, sub_server=sub, connected=connected
        )

        logger.info(
            "Mounted server '%s' (namespace=%s, readOnly=%s, connected=%s)",
            server_name,
            namespace,
            config.readOnly,
            connected,
        )

    return main, state
