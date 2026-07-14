# MCP Gateway projekt terv (v3)

A terv egy FastMCP 2.x alapú, streamable HTTP protokollt használó MCP gateway-t ír le, amely `config/mcpServers.json` konfigurációból több upstream MCP szervert (stdio, streamable-http, sse, websocket) aggregál, prefixál, szűr, környezeti változókat interpolál, automatikusan újratölt, és Docker image-ként a `ghcr.io/cociweb/mcp-gateway` címre pusholva érhető el.

## Főbb döntések

- **Projekt mappa**: `/home/cociweb/CascadeProjects/mcp-gateway`.
- **Repo és image**: `cociweb/mcp-gateway`, GHCR image `ghcr.io/cociweb/mcp-gateway`.
- **SDK**: `fastmcp>=2.8.0`, `mcp>=1.9.2`.
- **Config fájl**: `config/mcpServers.json` (cursor-ai stílusú JSON).
- **Gateway config**: környezeti változók `.env` fájlból és/vagy `docker-compose.yml` `environment:` szekcióból; változónevek `GATEWAY_*`. A szerver támogatja `0.0.0.0`, `127.0.0.1`, `localhost` bind-ot.
- **Docker Compose**: csak a gateway-t indítja, `mcp` Docker hálózat, `config/` volume, `.env` fájl.
- **readOnly**: `true` esetén tool-ok nem regisztrálódnak.
- **prefixTools**: `true` esetén `{namespace}_{tool}`.
- **Szűrők**: glob (`fnmatch`), `*` = minden.
- **Namespace**: hiányában a szerver kulcsa.
- **STDIO**: gateway konténerben fut (`npx`, `uvx`, stb.).

## Architektúra (moduláris)

- `gateway/main.py`: belépési pont, FastMCP szerver, route-ok.
- `gateway/config.py`: környezeti változókból tölti be a gateway beállításokat.
- `gateway/loader.py`: `mcpServers.json` parse, env interpoláció, validáció.
- `gateway/proxy.py`: upstream `Client` kezelés, aggregálás, routing.
- `gateway/transports/`: `streamable_http.py`, `stdio.py`, `sse.py`, `websocket.py`.
- `gateway/namespace.py`: prefix, filter, readOnly.
- `gateway/reconnect.py`: reconnect helper.
- `gateway/reload.py`: watchdog.
- `gateway/health.py`: `/health`, `/metrics`.
- `gateway/logging.py`: logolás.

## Konfigurációs séma

`config/mcpServers.json`:
- `mcpServers.<name>`: `type`, `enabled`, `url`, `command`, `args`, `env`, `headers`, `namespace`, `readOnly`, `prefixTools`, `toolFilter`, `resourceFilter`, `promptFilter`, `timeout`.

Környezeti változók (gateway):
- `GATEWAY_LISTEN` (default: `0.0.0.0`)
- `GATEWAY_PORT` (default: `5555`)
- `GATEWAY_PATH` (default: `/mcp`)
- `GATEWAY_RELOAD` (default: `true`)
- `GATEWAY_HEALTH_ENDPOINT` (default: `true`)
- `GATEWAY_METRICS` (default: `true`)
- `GATEWAY_LOG_LEVEL` (default: `info`)
- `GATEWAY_PREFIX_TOOLS` (default: `true`)
- `MCP_SERVERS_CONFIG` (default: `/app/config/mcpServers.json`)

A változókat a `.env` fájlban és/vagy a `docker-compose.yml` `environment:` szekcióban lehet állítani/felülírni; a `README` dokumentálja.

## Környezeti változók interpolálása

- Minden string mezőben `${VAR}` és `${VAR:-default}`.
- `os.environ` alapján; nem feloldható változó hibát dob.

## Aggregáció, prefix, szűrés

- `enabled=false` kihagyás.
- `prefixTools=true` → `{namespace}_{tool}`.
- `toolFilter`/`resourceFilter`/`promptFilter` glob.
- `readOnly=true` → tool-ok tiltása.

## Automatikus reload

- `watchdog` observer a `mcpServers.json` fájlra.
- Módosításkor: reload, reconnect, re-register, `list_changed` notifikáció.

## Health & metrics

- `/health` (vagy `/healthz`)
- `/metrics` Prometheus-like

## Docker / Compose

- `Dockerfile`: `python:3.12-slim`, `uv`, `node`, `fastmcp` install.
- `docker-compose.yml`: gateway service, `env_file: .env`, `environment:` felülírások, `config/` volume, `mcp` hálózat.
- `.env` minta.

## CI / GHCR

- `.github/workflows/ghcr.yml`: multi-platform build, push `ghcr.io/cociweb/mcp-gateway`.

## Fájlszerkezet

```
mcp-gateway/
├── .github/
│   └── workflows/
│       └── ghcr.yml
├── config/
│   └── mcpServers.json
├── gateway/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── loader.py
│   ├── proxy.py
│   ├── namespace.py
│   ├── reconnect.py
│   ├── reload.py
│   ├── logging.py
│   ├── health.py
│   └── transports/
│       ├── __init__.py
│       ├── streamable_http.py
│       ├── stdio.py
│       ├── sse.py
│       └── websocket.py
├── tests/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env
├── README.md
└── LICENSE
```

## Implementációs lépések

1. `pyproject.toml`
2. `config/mcpServers.json` minta
3. `.env` minta
4. `gateway/config.py`, `gateway/loader.py`
5. `gateway/transports/` modulok
6. `gateway/proxy.py`
7. `gateway/reload.py`
8. `gateway/health.py`
9. `gateway/main.py`
10. `Dockerfile`, `docker-compose.yml`, `README.md`, `LICENSE`
11. `.github/workflows/ghcr.yml`

## README tartalma

- Áttekintés, architektúra
- `.env` változók listája és default értékei
- `mcpServers.json` séma
- Docker Compose indítás
- stdio szerverek indítása
- GHCR image használata
- Fejlesztés/tesztelés
