"""Core data models for Obscura daemon."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal


class SyncStatus(str, Enum):
    """Cookie sync status."""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    ERROR = "error"


class SyncDirection(str, Enum):
    """Cookie sync direction."""
    SOURCE_TO_CACHE = "source_to_cache"
    CACHE_TO_SOURCE = "cache_to_source"
    BIDIRECTIONAL = "bidirectional"


class HookType(str, Enum):
    """Hook types for extensibility."""
    # Cookie sync hooks
    PRE_COOKIE_SYNC = "pre_cookie_sync"
    POST_COOKIE_SYNC = "post_cookie_sync"
    SYNC_CONFLICT = "sync_conflict"

    # Cookie extraction hooks
    PRE_COOKIE_EXTRACTION = "pre_cookie_extraction"
    POST_COOKIE_EXTRACTION = "post_cookie_extraction"

    # Browser lifecycle hooks
    PRE_BROWSER_LAUNCH = "pre_browser_launch"
    POST_BROWSER_LAUNCH = "post_browser_launch"

    # Validation hooks
    COOKIE_VALIDATION = "cookie_validation"
    AUTH_INVALIDATION = "auth_invalidation"

    # Connection pool hooks
    CONNECTION_POOL_ACQUIRE = "connection_pool_acquire"
    CONNECTION_POOL_RELEASE = "connection_pool_release"

    # Daemon lifecycle hooks
    DAEMON_STARTUP = "daemon_startup"
    DAEMON_SHUTDOWN = "daemon_shutdown"


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    source_hash: str
    cache_hash: str
    sync_direction: SyncDirection
    timestamp: str
    files_synced: int
    conflicts_resolved: int
    error_message: str | None = None


@dataclass
class SyncState:
    """Current sync state for a platform."""
    platform: str
    last_sync_time: str
    last_sync_direction: SyncDirection
    source_modified_time: str
    cache_modified_time: str
    sync_status: SyncStatus
    source_hash: str
    cache_hash: str


@dataclass
class BrowserRequirements:
    """Requirements for browser acquisition."""
    platform: str
    headless: bool = True
    proxy: str | None = None
    user_agent: str | None = None
    viewport: tuple[int, int] | None = None


@dataclass
class BrowserHandle:
    """Handle to a browser instance."""
    browser_id: str
    platform: str
    cdp_port: int
    pid: int
    created_at: str
    last_used_at: str


@dataclass
class PluginStatus:
    """Status of the plugin and daemon."""
    daemon_running: bool
    daemon_pid: int | None
    active_connections: int
    synced_platforms: list[str]
    last_health_check: str
    error_message: str | None = None


@dataclass
class Hook:
    """Hook registration."""
    hook_type: HookType
    callback_id: str
    priority: int = 0
    platform: str | None = None  # None means applies to all platforms


@dataclass
class DaemonConfig:
    """Daemon configuration."""
    host: str = "127.0.0.1"
    port: int = 9999
    max_connections: int = 10
    connection_idle_timeout: int = 300  # seconds
    connection_lifetime: int = 1800  # seconds
    sync_interval: int = 5  # seconds
    cookie_validation_interval: int = 300  # seconds
    log_level: str = "INFO"

    # Storage paths
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".obscura" / "cache")
    config_dir: Path = field(default_factory=lambda: Path.home() / ".obscura" / "config")
    log_dir: Path = field(default_factory=lambda: Path.home() / ".obscura" / "logs")

    # Platform-specific source paths
    source_paths: dict[str, Path] = field(default_factory=lambda: {
        "linkedin": Path.home() / ".linkedin-lyr" / "cookies.json",
        "instagram": Path.home() / ".instagram-lyr" / "cookies.json",
        "reddit": Path.home() / ".reddit-lyr" / "cookies.json",
        "twitter": Path.home() / ".local" / "share" / "twitter-lyr" / "cookies.json",
    })
