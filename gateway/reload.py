"""Watches ``mcpServers.json`` for changes and triggers a reload callback.

The gateway's mounted-server tree (and the underlying HTTP app's ASGI
lifespan, which starts FastMCP's streamable-HTTP session manager) is only
safely rebuilt by re-running the full startup sequence. Rather than trying to
hot-swap live ASGI apps/lifespans in place, on a detected change this module
asks :mod:`gateway.main` to gracefully restart the gateway process in-place
(``os.execv``), which re-reads the (possibly changed) config, reconnects to
all upstream servers, re-registers everything, and clients simply reconnect
(streamable-HTTP clients are expected to retry/reconnect on disconnect).
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .logging import get_logger

logger = get_logger(__name__)

_DEBOUNCE_SECONDS = 0.75


class _ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config_path: Path, on_change: Callable[[], None]) -> None:
        self._config_path = config_path.resolve()
        self._on_change = on_change
        self._last_triggered = 0.0
        self._lock = threading.Lock()

    def _maybe_trigger(self, event: FileSystemEvent) -> None:
        try:
            src_path = Path(str(event.src_path)).resolve()
        except OSError:
            return
        if src_path != self._config_path:
            return

        with self._lock:
            now = time.monotonic()
            if now - self._last_triggered < _DEBOUNCE_SECONDS:
                return
            self._last_triggered = now

        logger.info("Detected change in %s", self._config_path)
        self._on_change()

    def on_modified(self, event: FileSystemEvent) -> None:
        self._maybe_trigger(event)

    def on_created(self, event: FileSystemEvent) -> None:
        self._maybe_trigger(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._maybe_trigger(event)


class ConfigReloader:
    """Watches the directory containing ``config_path`` for changes to it."""

    def __init__(
        self,
        config_path: str | Path,
        on_change: Callable[[], Coroutine[Any, Any, None]],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._config_path = Path(config_path)
        self._on_change = on_change
        self._loop = loop or asyncio.get_event_loop()
        self._observer = Observer()

    def _schedule_callback(self) -> None:
        asyncio.run_coroutine_threadsafe(self._on_change(), self._loop)

    def start(self) -> None:
        watch_dir = self._config_path.parent
        if not watch_dir.is_dir():
            logger.warning(
                "Config directory %s does not exist; reload watcher disabled",
                watch_dir,
            )
            return

        handler = _ConfigFileHandler(self._config_path, self._schedule_callback)
        self._observer.schedule(handler, str(watch_dir), recursive=False)
        self._observer.start()
        logger.info("Watching %s for changes", self._config_path)

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=2)
