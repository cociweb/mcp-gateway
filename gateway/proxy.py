"""Builds the aggregated gateway FastMCP server from ``mcpServers.json``.

For every enabled upstream server, a :class:`fastmcp.FastMCP` proxy
sub-server is created (via ``FastMCPProxy`` with an explicit
``client_factory`` that builds a fresh transport per call, see
``build_gateway`` for why) with a per-server
:class:`~gateway.namespace.ServerFilterMiddleware` attached, then mounted
onto the main gateway server with ``namespace=<effective_namespace>`` when
``prefixTools`` is enabled (or without a namespace otherwise).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastmcp import Client, FastMCP
from fastmcp.server.providers.proxy import FastMCPProxy

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
            build_transport(config)
        except ValueError as exc:
            logger.error("Skipping server '%s': %s", server_name, exc)
            continue

        # Build a fresh transport (and Client) on every call instead of
        # sharing a single transport instance across concurrent requests.
        # create_proxy()'s default session strategy only guarantees a fresh
        # *session* per call (via Client.new()) while still reusing the same
        # underlying transport/connection object; concurrent calls sharing
        # that transport can corrupt each other's auth/session state against
        # stateful or strict upstream servers (observed as spurious 401s).
        def _make_client(config: ServerConfig = config) -> Client:
            return Client(build_transport(config), timeout=config.timeout)

        sub = FastMCPProxy(client_factory=_make_client, name=server_name)
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
