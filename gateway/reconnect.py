"""Reconnect helper: retries a coroutine with exponential backoff.

Used to probe upstream MCP servers at startup/reload without blocking the
gateway from starting if one of them is temporarily unavailable.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def retry_with_backoff(
    factory: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    initial_delay: float = 0.5,
    max_delay: float = 8.0,
    label: str = "operation",
) -> T | None:
    """Retry an async ``factory`` call with exponential backoff.

    Returns the result on success, or ``None`` if all attempts fail (the
    failure is logged as a warning rather than raised, so callers can decide
    to continue running the gateway in a degraded state).
    """
    delay = initial_delay
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            return await factory()
        except Exception as exc:  # noqa: BLE001 - upstream errors are varied
            last_exc = exc
            logger.warning(
                "%s failed (attempt %d/%d): %s", label, attempt, retries, exc
            )
            if attempt < retries:
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

    logger.error("%s failed after %d attempts: %s", label, retries, last_exc)
    return None
