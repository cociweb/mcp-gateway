"""Per-server namespace enforcement: prefix, glob filters and readOnly.

Prefixing itself is delegated to ``FastMCP.mount(..., namespace=...)``; this
module provides the middleware that enforces ``toolFilter`` /
``resourceFilter`` / ``promptFilter`` (glob patterns) and ``readOnly`` on a
per-upstream-server basis, applied to the proxy sub-server *before* it is
mounted onto the main gateway server.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Sequence

from fastmcp.exceptions import PromptError, ResourceError, ToolError
from fastmcp.prompts.prompt import Prompt
from fastmcp.resources.resource import Resource
from fastmcp.resources.template import ResourceTemplate
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools.tool import Tool

from .loader import ServerConfig
from .logging import get_logger

logger = get_logger(__name__)


def matches_any(name: str, patterns: Sequence[str]) -> bool:
    """Glob match ``name`` against ``patterns`` (``fnmatch``, ``*`` = all)."""
    if not patterns:
        return False
    return any(fnmatch(name, pattern) for pattern in patterns)


class ServerFilterMiddleware(Middleware):
    """Enforces a single upstream server's readOnly flag and glob filters.

    Attached to the proxy sub-server created for that upstream *before* it is
    mounted onto the main gateway server, so it runs for every request
    forwarded through the mount.
    """

    def __init__(self, config: ServerConfig) -> None:
        self.config = config

    # -- tools ----------------------------------------------------------
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        if self.config.readOnly:
            return []
        tools: Sequence[Tool] = await call_next(context)
        return [t for t in tools if matches_any(t.name, self.config.toolFilter)]

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        name = context.message.name
        if self.config.readOnly or not matches_any(name, self.config.toolFilter):
            raise ToolError(
                f"Tool '{name}' is not available on server "
                f"'{self.config.name}' (readOnly={self.config.readOnly})"
            )
        return await call_next(context)

    # -- resources --------------------------------------------------------
    async def on_list_resources(self, context: MiddlewareContext, call_next):
        resources: Sequence[Resource] = await call_next(context)
        return [
            r
            for r in resources
            if matches_any(str(r.uri), self.config.resourceFilter)
        ]

    async def on_list_resource_templates(self, context: MiddlewareContext, call_next):
        templates: Sequence[ResourceTemplate] = await call_next(context)
        return [
            t
            for t in templates
            if matches_any(str(t.uri_template), self.config.resourceFilter)
        ]

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        uri = str(context.message.uri)
        if not matches_any(uri, self.config.resourceFilter):
            raise ResourceError(
                f"Resource '{uri}' is not available on server '{self.config.name}'"
            )
        return await call_next(context)

    # -- prompts ----------------------------------------------------------
    async def on_list_prompts(self, context: MiddlewareContext, call_next):
        prompts: Sequence[Prompt] = await call_next(context)
        return [p for p in prompts if matches_any(p.name, self.config.promptFilter)]

    async def on_get_prompt(self, context: MiddlewareContext, call_next):
        name = context.message.name
        if not matches_any(name, self.config.promptFilter):
            raise PromptError(
                f"Prompt '{name}' is not available on server '{self.config.name}'"
            )
        return await call_next(context)


def build_filter_middleware(config: ServerConfig) -> ServerFilterMiddleware:
    return ServerFilterMiddleware(config)
