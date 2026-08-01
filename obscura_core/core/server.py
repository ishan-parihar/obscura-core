"""FastAPI server for Obscura daemon HTTP API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel
from loguru import logger

from obscura_core.core.daemon import ObscuraDaemon
from obscura_core.core.models import (
    BrowserHandle,
    BrowserRequirements,
    DaemonConfig,
    HookType,
    PluginStatus,
)


class ReleaseBrowserRequest(BaseModel):
    """Request model for releasing a browser."""
    browser_id: str


class RegisterHookRequest(BaseModel):
    """Request model for registering a hook."""
    hook_type: str
    callback_url: str
    priority: int = 0
    platform: str | None = None


class UnregisterHookRequest(BaseModel):
    """Request model for unregistering a hook."""
    hook_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    daemon: ObscuraDaemon = app.state.daemon
    await daemon.start()
    yield
    await daemon.stop()


def create_app(daemon: ObscuraDaemon) -> FastAPI:
    """Create FastAPI application with daemon integration."""
    app = FastAPI(
        title="Obscura Daemon",
        description="Centralized daemon for Obscura browser integration",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.daemon = daemon

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "daemon_running": daemon._running}

    @app.get("/api/v1/status")
    async def get_status() -> PluginStatus:
        """Get daemon status."""
        return await daemon.get_status()

    @app.post("/api/v1/browser/acquire")
    async def acquire_browser(requirements: BrowserRequirements) -> BrowserHandle:
        """Acquire a browser from the connection pool."""
        return await daemon.acquire_browser(requirements)

    @app.post("/api/v1/browser/release")
    async def release_browser(request: ReleaseBrowserRequest) -> dict:
        """Release a browser back to the connection pool."""
        await daemon.release_browser(request.browser_id)
        return {"success": True}

    @app.get("/api/v1/cookies/{platform}")
    async def get_cookies(platform: str) -> dict[str, str] | None:
        """Get cookies for a platform from the cache."""
        return await daemon.get_cookies(platform)

    @app.post("/api/v1/sync/{platform}")
    async def sync_cookies(platform: str) -> dict:
        """Trigger cookie sync for a platform."""
        return await daemon.sync_cookies(platform)

    @app.post("/api/v1/hooks/register")
    async def register_hook(request: RegisterHookRequest) -> dict:
        """Register a webhook callback for a hook type."""
        hook_id = await daemon.hook_system.register(
            HookType(request.hook_type),
            lambda ctx: logger.info(f"Hook {hook_id} triggered: {ctx}"),
            request.priority,
            request.platform,
        )
        return {"hook_id": hook_id}

    @app.post("/api/v1/hooks/unregister")
    async def unregister_hook(request: UnregisterHookRequest) -> dict:
        """Unregister a hook callback."""
        success = await daemon.hook_system.unregister(request.hook_id)
        return {"success": success}

    return app
