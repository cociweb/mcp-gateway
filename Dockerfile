FROM python:3.12-slim AS base

# Node.js (for `npx`-based stdio MCP servers) and uv (for `uvx`-based ones).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml ./
COPY README.md ./
COPY gateway ./gateway
COPY config ./config

RUN uv pip install --system --no-cache .

ENV MCP_SERVERS_CONFIG=/app/config/mcpServers.json \
    GATEWAY_LISTEN=0.0.0.0 \
    GATEWAY_PORT=5555 \
    GATEWAY_PATH=/mcp \
    PYTHONUNBUFFERED=1

EXPOSE 5555

ENTRYPOINT ["python", "-m", "gateway.main"]
