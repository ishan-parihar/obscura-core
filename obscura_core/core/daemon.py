"""Core Obscura daemon implementation."""

from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from obscura_core.core.models import (
    BrowserHandle,
    BrowserRequirements,
    DaemonConfig,
    HookType,
    PluginStatus,
)
from obscura_core.hooks.hook_system import HookSystem
from obscura_core.pool.connection_pool import ConnectionPoolManager
from obscura_core.sync.cookie_sync import CookieSyncManager


class ObscuraDaemon:
    """Main Obscura daemon for centralized browser integration."""

    def __init__(self, config: DaemonConfig | None = None) -> None:
        self.config = config or DaemonConfig()
        self.cookie_sync = CookieSyncManager(self.config)
        self.connection_pool = ConnectionPoolManager(self.config)
        self.hook_system = HookSystem()
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Setup logging
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            self.config.log_dir / "daemon.log",
            rotation="10 MB",
            retention="7 days",
            level=self.config.log_level,
        )

    async def start(self) -> None:
        """Start the daemon and all its components."""
        if self._running:
            logger.warning("Daemon already running")
            return

        logger.info("Starting Obscura daemon")
        self._running = True

        # Start components
        await self.cookie_sync.start()
        await self.connection_pool.start()

        # Trigger startup hooks
        await self.hook_system.trigger(HookType.DAEMON_STARTUP, {"timestamp": datetime.now().isoformat()})

        logger.info("Obscura daemon started successfully")

    async def stop(self) -> None:
        """Stop the daemon and all its components."""
        if not self._running:
            return

        logger.info("Stopping Obscura daemon")

        # Trigger shutdown hooks
        await self.hook_system.trigger(HookType.DAEMON_SHUTDOWN, {"timestamp": datetime.now().isoformat()})

        # Stop components
        await self.connection_pool.stop()
        await self.cookie_sync.stop()

        self._running = False
        self._shutdown_event.set()
        logger.info("Obscura daemon stopped")

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    async def acquire_browser(self, requirements: BrowserRequirements) -> BrowserHandle:
        """Acquire a browser from the connection pool."""
        return await self.connection_pool.acquire(requirements)

    async def release_browser(self, browser_id: str) -> None:
        """Release a browser back to the connection pool."""
        await self.connection_pool.release(browser_id)

    async def get_cookies(self, platform: str) -> dict[str, str] | None:
        """Get cookies for a platform from the cache."""
        return await self.cookie_sync.get_cookies_from_cache(platform)

    async def sync_cookies(self, platform: str) -> dict:
        """Trigger cookie sync for a platform."""
        result = await self.cookie_sync.sync_to_cache(platform)
        return {
            "success": result.success,
            "source_hash": result.source_hash,
            "cache_hash": result.cache_hash,
            "sync_direction": result.sync_direction.value,
            "timestamp": result.timestamp,
            "files_synced": result.files_synced,
            "conflicts_resolved": result.conflicts_resolved,
            "error_message": result.error_message,
        }

    async def get_status(self) -> PluginStatus:
        """Get daemon status."""
        pool_status = await self.connection_pool.get_status()
        synced_platforms = []

        for platform in self.config.source_paths:
            state = await self.cookie_sync.get_sync_state(platform)
            if state and state.sync_status.value == "synced":
                synced_platforms.append(platform)

        return PluginStatus(
            daemon_running=self._running,
            daemon_pid=None,  # Will be set by the process manager
            active_connections=pool_status["acquired"],
            synced_platforms=synced_platforms,
            last_health_check=datetime.now().isoformat(),
        )


@asynccontextmanager
async def daemon_context(config: DaemonConfig | None = None):
    """Context manager for running the daemon."""
    daemon = ObscuraDaemon(config)
    try:
        await daemon.start()
        yield daemon
    finally:
        await daemon.stop()
