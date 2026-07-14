"""Integration test: mounts a real stdio MCP server (npx filesystem server)
and exercises prefixing, toolFilter and readOnly enforcement end-to-end.

Skipped automatically if `npx` is not available in the environment.
"""

from __future__ import annotations

import shutil

import pytest

from gateway.loader import ServerConfig
from gateway.proxy import build_gateway

pytestmark = pytest.mark.skipif(
    shutil.which("npx") is None, reason="npx not available"
)


def _fs_server_config(tmp_path, **overrides) -> ServerConfig:
    defaults = dict(
        name="filesystem",
        type="stdio",
        enabled=True,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", str(tmp_path)],
        namespace="fs",
        readOnly=False,
        prefixTools=True,
        toolFilter=["*"],
    )
    defaults.update(overrides)
    return ServerConfig(**defaults)


@pytest.mark.asyncio
async def test_mounted_tools_are_prefixed(tmp_path) -> None:
    servers = {"filesystem": _fs_server_config(tmp_path)}
    gw, state = await build_gateway(servers, probe=False)

    tools = await gw.list_tools()
    names = [t.name for t in tools]

    assert names, "expected at least one tool from the mounted filesystem server"
    assert all(name.startswith("fs_") for name in names)
    assert state.enabled_count == 1


@pytest.mark.asyncio
async def test_tool_filter_restricts_visible_tools(tmp_path) -> None:
    servers = {
        "filesystem": _fs_server_config(tmp_path, toolFilter=["*read*"]),
    }
    gw, _ = await build_gateway(servers, probe=False)

    tools = await gw.list_tools()
    names = [t.name for t in tools]

    assert names, "expected at least one 'read' tool"
    assert all("read" in name for name in names)


@pytest.mark.asyncio
async def test_read_only_hides_all_tools(tmp_path) -> None:
    servers = {
        "filesystem": _fs_server_config(tmp_path, readOnly=True),
    }
    gw, _ = await build_gateway(servers, probe=False)

    tools = await gw.list_tools()
    assert tools == []


@pytest.mark.asyncio
async def test_call_tool_end_to_end(tmp_path) -> None:
    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    servers = {"filesystem": _fs_server_config(tmp_path)}
    gw, _ = await build_gateway(servers, probe=False)

    result = await gw.call_tool("fs_list_directory", {"path": str(tmp_path)})
    assert result is not None
