"""Plugin client for CLI tools to interact with Obscura daemon."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Self

import httpx
from loguru import logger

from obscura_daemon.core.models import (
    BrowserHandle,
    BrowserRequirements,
    HookType,
    PluginStatus,
)


class ObscuraPlugin:
    """Main plugin interface for CLI tools to interact with Obscura daemon."""

    def __init__(self, daemon_url: str = "http://127.0.0.1:9999") -> None:
        self.daemon_url = daemon_url
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Connect to the daemon."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"Connected to Obscura daemon at {self.daemon_url}")

    async def close(self) -> None:
        """Close the connection to the daemon."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Closed connection to Obscura daemon")

    async def acquire_browser(
        self,
        platform: str,
        requirements: BrowserRequirements | None = None,
    ) -> BrowserHandle:
        """Acquire a browser instance from the pool."""
        if requirements is None:
            requirements = BrowserRequirements(platform=platform)

        if not self._client:
            raise RuntimeError("Not connected to daemon")

        response = await self._client.post(
            f"{self.daemon_url}/api/v1/browser/acquire",
            json={
                "platform": requirements.platform,
                "headless": requirements.headless,
                "proxy": requirements.proxy,
                "user_agent": requirements.user_agent,
                "viewport": requirements.viewport,
            },
        )
        response.raise_for_status()
        data = response.json()

        return BrowserHandle(
            browser_id=data["browser_id"],
            platform=data["platform"],
            cdp_port=data["cdp_port"],
            pid=data["pid"],
            created_at=data["created_at"],
            last_used_at=data["last_used_at"],
        )

    async def release_browser(self, browser_id: str) -> None:
        """Release a browser instance back to the pool."""
        if not self._client:
            raise RuntimeError("Not connected to daemon")

        response = await self._client.post(
            f"{self.daemon_url}/api/v1/browser/release",
            json={"browser_id": browser_id},
        )
        response.raise_for_status()

    async def get_cookies(self, platform: str) -> dict[str, str] | None:
        """Get cookies for a platform from shared storage."""
        if not self._client:
            raise RuntimeError("Not connected to daemon")

        response = await self._client.get(f"{self.daemon_url}/api/v1/cookies/{platform}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def validate_cookies(self, platform: str, cookies: dict[str, str]) -> bool:
        """Validate cookies for a platform."""
        if not self._client:
            raise RuntimeError("Not connected to daemon")

        response = await self._client.post(
            f"{self.daemon_url}/api/v1/cookies/{platform}/validate",
            json=cookies,
        )
        response.raise_for_status()
        return response.json()["valid"]

    async def register_hook(
        self,
        hook_type: HookType,
        callback_url: str,
        priority: int = 0,
        platform: str | None = None,
    ) -> str:
        """Register a webhook callback for a hook type."""
        if not self._client:
            raise RuntimeError("Not connected to daemon")

        response = await self._client.post(
            f"{self.daemon_url}/api/v1/hooks/register",
            json={
                "hook_type": hook_type.value,
                "callback_url": callback_url,
                "priority": priority,
                "platform": platform,
            },
        )
        response.raise_for_status()
        return response.json()["hook_id"]

    async def unregister_hook(self, hook_id: str) -> bool:
        """Unregister a hook callback."""
        if not self._client:
            raise RuntimeError("Not connected to daemon")

        response = await self._client.post(
            f"{self.daemon_url}/api/v1/hooks/unregister",
            json={"hook_id": hook_id},
        )
        response.raise_for_status()
        return response.json()["success"]

    async def get_status(self) -> PluginStatus:
        """Get plugin and daemon status."""
        if not self._client:
            raise RuntimeError("Not connected to daemon")

        response = await self._client.get(f"{self.daemon_url}/api/v1/status")
        response.raise_for_status()
        data = response.json()

        return PluginStatus(
            daemon_running=data["daemon_running"],
            daemon_pid=data.get("daemon_pid"),
            active_connections=data["active_connections"],
            synced_platforms=data["synced_platforms"],
            last_health_check=data["last_health_check"],
            error_message=data.get("error_message"),
        )

    async def sync_cookies(self, platform: str) -> dict:
        """Trigger cookie sync for a platform."""
        if not self._client:
            raise RuntimeError("Not connected to daemon")

        response = await self._client.post(f"{self.daemon_url}/api/v1/sync/{platform}")
        response.raise_for_status()
        return response.json()
