"""``/health`` and ``/metrics`` endpoints for the gateway.

These are registered as custom Starlette routes on the *main* FastMCP server
so they are served from the same HTTP app as the MCP endpoint.
"""

from __future__ import annotations

import time

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from .proxy import GatewayState

_START_TIME = time.monotonic()


def register_health_routes(
    main: FastMCP,
    state_ref: dict[str, GatewayState],
    *,
    health_enabled: bool,
    metrics_enabled: bool,
) -> None:
    """Register ``/health`` and ``/metrics`` routes on ``main``.

    ``state_ref`` is a single-item mutable dict (``{"state": GatewayState}``)
    so that a config reload can atomically swap in a fresh
    :class:`GatewayState` without needing to re-register routes.
    """

    if health_enabled:

        @main.custom_route("/health", methods=["GET"])
        async def health(_: Request) -> JSONResponse:  # noqa: ANN001
            state = state_ref["state"]
            return JSONResponse(
                {
                    "status": "ok",
                    "uptime_seconds": round(time.monotonic() - _START_TIME, 3),
                    "servers_enabled": state.enabled_count,
                    "servers_connected": state.connected_count,
                    "servers": {
                        name: {
                            "namespace": m.config.effective_namespace,
                            "type": m.config.type,
                            "readOnly": m.config.readOnly,
                            "prefixTools": m.config.prefixTools,
                            "connected": m.connected,
                        }
                        for name, m in state.mounted.items()
                    },
                }
            )

        @main.custom_route("/healthz", methods=["GET"])
        async def healthz(_: Request) -> PlainTextResponse:  # noqa: ANN001
            return PlainTextResponse("ok")

    if metrics_enabled:

        @main.custom_route("/metrics", methods=["GET"])
        async def metrics(_: Request) -> PlainTextResponse:  # noqa: ANN001
            state = state_ref["state"]
            lines = [
                "# HELP mcp_gateway_uptime_seconds Gateway process uptime in seconds",
                "# TYPE mcp_gateway_uptime_seconds gauge",
                f"mcp_gateway_uptime_seconds {round(time.monotonic() - _START_TIME, 3)}",
                "# HELP mcp_gateway_servers_enabled Number of enabled upstream servers",
                "# TYPE mcp_gateway_servers_enabled gauge",
                f"mcp_gateway_servers_enabled {state.enabled_count}",
                "# HELP mcp_gateway_servers_connected Number of upstream servers reachable at last probe",
                "# TYPE mcp_gateway_servers_connected gauge",
                f"mcp_gateway_servers_connected {state.connected_count}",
                "# HELP mcp_gateway_server_connected Per-server connectivity (1=connected, 0=not)",
                "# TYPE mcp_gateway_server_connected gauge",
            ]
            for name, m in state.mounted.items():
                lines.append(
                    f'mcp_gateway_server_connected{{server="{name}"}} {int(m.connected)}'
                )
            return PlainTextResponse("\n".join(lines) + "\n")
