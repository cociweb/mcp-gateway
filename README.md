# MCP Gateway

A [FastMCP](https://gofastmcp.com) 2.x-based gateway that aggregates multiple
upstream [Model Context Protocol](https://modelcontextprotocol.io) servers
(stdio, streamable-http, sse, websocket) behind a single streamable-HTTP
endpoint. Upstream servers are configured declaratively in
`config/mcpServers.json`, with per-server namespacing, tool/resource/prompt
filtering, read-only enforcement, environment-variable interpolation, and
automatic reload on config changes.

## Architecture

```
gateway/
├── main.py             # entrypoint: builds & serves the gateway, wires reload
├── config.py            # GatewayConfig, loaded from environment variables
├── loader.py             # mcpServers.json parsing, env interpolation, validation
├── proxy.py              # builds the aggregated FastMCP server (mount per upstream)
├── namespace.py          # per-server middleware: toolFilter/resourceFilter/promptFilter, readOnly
├── reconnect.py           # retry-with-backoff helper used for upstream connectivity probes
├── reload.py              # watchdog-based watcher for mcpServers.json
├── health.py              # /health, /healthz, /metrics routes
├── logging.py             # logging setup
└── transports/
    ├── stdio.py            # spawns local processes (npx, uvx, ...)
    ├── streamable_http.py  # streamable-HTTP upstream client transport
    ├── sse.py              # SSE upstream client transport
    └── websocket.py        # WebSocket upstream client transport (custom, mcp SDK based)
```

Each enabled upstream server becomes a FastMCP proxy sub-server
(`fastmcp.server.create_proxy`), gets a `ServerFilterMiddleware` attached
(enforcing `readOnly` / `toolFilter` / `resourceFilter` / `promptFilter`), and
is mounted onto the main gateway server with `namespace=<namespace>` when
`prefixTools` is enabled. Tool/resource/prompt names are then automatically
namespaced by FastMCP as `{namespace}_{name}`.

## Configuration

### `config/mcpServers.json`

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "enabled": true,
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${FS_ROOT:-/data}"],
      "env": {},
      "namespace": "fs",
      "readOnly": false,
      "prefixTools": true,
      "toolFilter": ["*"],
      "resourceFilter": ["*"],
      "promptFilter": ["*"],
      "timeout": 30
    }
  }
}
```

Field reference per server entry:

| Field | Type | Description |
|---|---|---|
| `type` | `stdio` \| `streamable-http` \| `sse` \| `websocket` | Upstream transport kind |
| `enabled` | bool | If `false`, the server is skipped entirely |
| `url` | string | Required for `streamable-http` / `sse` / `websocket` |
| `command`, `args`, `env` | - | Required for `stdio` (e.g. `npx`, `uvx`) |
| `headers` | object | Extra HTTP headers for `streamable-http` / `sse` |
| `namespace` | string | Prefix used for this server's tools/resources/prompts; defaults to the server's key |
| `readOnly` | bool | If `true`, **no tools** from this server are registered |
| `prefixTools` | bool | If `true`, tools become `{namespace}_{tool}` |
| `toolFilter` / `resourceFilter` / `promptFilter` | list of glob patterns | `fnmatch`-style; `["*"]` = allow all |
| `timeout` | number | Per-call timeout (seconds) for the upstream connection probe |

Any string value in the file supports `${VAR}` / `${VAR:-default}`
interpolation, resolved against the process environment (`.env` +
`docker-compose.yml` `environment:`). An unresolved variable without a
default raises a configuration error for *enabled* servers; disabled server
entries with unresolved variables are tolerated (logged as a warning).

### Environment variables (`.env` / `docker-compose.yml`)

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_LISTEN` | `0.0.0.0` | Bind address (`0.0.0.0`, `127.0.0.1`, `localhost` supported) |
| `GATEWAY_PORT` | `5555` | Bind port |
| `GATEWAY_PATH` | `/mcp` | HTTP path for the MCP streamable-HTTP endpoint |
| `GATEWAY_RELOAD` | `true` | Watch `mcpServers.json` and restart the process on change |
| `GATEWAY_HEALTH_ENDPOINT` | `true` | Enable `/health` and `/healthz` |
| `GATEWAY_METRICS` | `true` | Enable `/metrics` (Prometheus text format) |
| `GATEWAY_LOG_LEVEL` | `info` | `debug` \| `info` \| `warning` \| `error` \| `critical` |
| `GATEWAY_PREFIX_TOOLS` | `true` | Default for `prefixTools` when a server entry omits it |
| `MCP_SERVERS_CONFIG` | `/app/config/mcpServers.json` | Path to the servers config file |

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env .env.local   # adjust as needed
export $(grep -v '^#' .env.local | xargs)
python -m gateway.main
```

The gateway will be reachable at `http://localhost:5555/mcp`, with
`http://localhost:5555/health` and `http://localhost:5555/metrics` alongside it.

### stdio upstream servers

`stdio` servers (`npx`, `uvx`, ...) are spawned as subprocesses *inside* the
gateway process/container — no separate container or network hop is needed.
Make sure `node`/`npx` and/or `uv`/`uvx` are available in the runtime
environment (the provided `Dockerfile` installs both).

## Docker Compose

```bash
docker compose up -d --build
```

This starts only the gateway service, on the `mcp` Docker network, mounting
`./config` read-only and loading `./.env`. To use the published image instead
of building locally:

```bash
docker pull ghcr.io/cociweb/mcp-gateway:latest
docker compose up -d
```

## Reload behavior

When `GATEWAY_RELOAD=true`, a `watchdog` observer watches the directory
containing `mcpServers.json`. On any change to that file, the gateway
gracefully restarts itself in-place (`os.execv`) to rebuild the full mounted
server tree (reconnect upstreams, reapply filters/prefixes). Streamable-HTTP
clients are expected to reconnect automatically on disconnect.

## Health & metrics

- `GET /health` — JSON status, per-server connectivity and config summary.
- `GET /healthz` — plain-text `ok` liveness probe.
- `GET /metrics` — Prometheus-style text exposition (uptime, enabled/connected
  server counts, per-server connectivity gauge).

## Development / testing

```bash
pip install -e ".[dev]"
pytest -q
```

`tests/test_proxy_integration.py` spins up a real `npx`-based MCP filesystem
server and is skipped automatically if `npx` is not available.

## CI / GHCR

`.github/workflows/ghcr.yml` builds a multi-platform (`linux/amd64`,
`linux/arm64`) image and pushes it to `ghcr.io/cociweb/mcp-gateway` on pushes
to `main` and on version tags.
