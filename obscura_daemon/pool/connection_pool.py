"""Connection pool manager for Obscura browser instances."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self

from loguru import logger

from obscura_daemon.core.models import (
    BrowserHandle,
    BrowserRequirements,
    DaemonConfig,
)


@dataclass
class PooledConnection:
    """A pooled browser connection."""
    handle: BrowserHandle
    requirements: BrowserRequirements
    acquired: bool = False
    acquire_time: datetime | None = None
    last_activity: datetime = field(default_factory=datetime.now)


class ConnectionPoolManager:
    """Manages a pool of browser connections with dynamic port allocation."""

    def __init__(self, config: DaemonConfig) -> None:
        self.config = config
        self.pool: dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._next_port = 9500  # Start port for dynamic allocation
        self._cleanup_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the connection pool manager."""
        if self._running:
            logger.warning("ConnectionPoolManager already running")
            return

        self._running = True
        logger.info("Starting ConnectionPoolManager")

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the connection pool manager."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping ConnectionPoolManager")

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        async with self._lock:
            for conn_id, conn in list(self.pool.items()):
                await self._close_connection(conn_id, conn)
            self.pool.clear()

    async def acquire(self, requirements: BrowserRequirements) -> BrowserHandle:
        """Acquire a browser connection from the pool."""
        async with self._lock:
            # Try to find an available connection matching requirements
            for conn_id, conn in self.pool.items():
                if (
                    not conn.acquired
                    and conn.requirements.platform == requirements.platform
                    and conn.requirements.headless == requirements.headless
                ):
                    # Check if connection is still valid (not too old)
                    age = (datetime.now() - conn.handle.created_at).total_seconds()
                    if age < self.config.connection_lifetime:
                        conn.acquired = True
                        conn.acquire_time = datetime.now()
                        conn.last_activity = datetime.now()
                        logger.info(f"Acquired existing connection {conn_id} for {requirements.platform}")
                        return conn.handle

            # No available connection, create a new one
            port = self._allocate_port()
            handle = await self._create_browser(requirements, port)

            pooled = PooledConnection(
                handle=handle,
                requirements=requirements,
                acquired=True,
                acquire_time=datetime.now(),
                last_activity=datetime.now(),
            )
            self.pool[handle.browser_id] = pooled

            logger.info(f"Created new connection {handle.browser_id} for {requirements.platform} on port {port}")
            return handle

    async def release(self, browser_id: str) -> None:
        """Release a browser connection back to the pool."""
        async with self._lock:
            conn = self.pool.get(browser_id)
            if not conn:
                logger.warning(f"Connection {browser_id} not found in pool")
                return

            conn.acquired = False
            conn.acquire_time = None
            conn.last_activity = datetime.now()
            logger.info(f"Released connection {browser_id}")

    async def get_status(self) -> dict[str, int]:
        """Get connection pool status."""
        async with self._lock:
            total = len(self.pool)
            acquired = sum(1 for conn in self.pool.values() if conn.acquired)
            idle = total - acquired
            return {"total": total, "acquired": acquired, "idle": idle}

    def _allocate_port(self) -> int:
        """Allocate a dynamic port for CDP server."""
        port = self._next_port
        self._next_port += 1
        # Wrap around if we exceed the range
        if self._next_port > 9999:
            self._next_port = 9500
        return port

    async def _create_browser(self, requirements: BrowserRequirements, port: int) -> BrowserHandle:
        """Create a new browser instance (placeholder for actual implementation)."""
        # This is a placeholder - actual implementation would launch Obscura
        # or a browser instance with the specified CDP port
        browser_id = str(uuid.uuid4())

        # TODO: Implement actual browser creation using obscura_cookie_manager
        # For now, return a mock handle
        logger.warning("Browser creation not yet implemented - returning mock handle")

        return BrowserHandle(
            browser_id=browser_id,
            platform=requirements.platform,
            cdp_port=port,
            pid=0,  # Placeholder
            created_at=datetime.now().isoformat(),
            last_used_at=datetime.now().isoformat(),
        )

    async def _close_connection(self, conn_id: str, conn: PooledConnection) -> None:
        """Close a browser connection."""
        # TODO: Implement actual browser termination
        logger.info(f"Closing connection {conn_id}")

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of idle connections."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_idle(self) -> None:
        """Clean up idle connections that have exceeded timeout."""
        async with self._lock:
            now = datetime.now()
            to_remove = []

            for conn_id, conn in self.pool.items():
                if not conn.acquired:
                    idle_time = (now - conn.last_activity).total_seconds()
                    if idle_time > self.config.connection_idle_timeout:
                        to_remove.append(conn_id)

            for conn_id in to_remove:
                conn = self.pool.pop(conn_id)
                await self._close_connection(conn_id, conn)
                logger.info(f"Cleaned up idle connection {conn_id}")
