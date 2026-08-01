"""Cookie synchronization manager for replicating cookies between source and cache."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Self

from loguru import logger
from watchfiles import awatch

from obscura_daemon.core.models import (
    DaemonConfig,
    SyncDirection,
    SyncResult,
    SyncState,
    SyncStatus,
)


class CookieSyncManager:
    """Manages cookie synchronization between source locations and daemon cache."""

    def __init__(self, config: DaemonConfig) -> None:
        self.config = config
        self.cache_dir = config.cache_dir / "cookies"
        self.sync_state_dir = config.cache_dir / "sync_state"
        self.file_watchers: dict[str, asyncio.Task[None]] = {}
        self._running = False

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sync_state_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        """Start the sync manager and begin watching files."""
        if self._running:
            logger.warning("CookieSyncManager already running")
            return

        self._running = True
        logger.info("Starting CookieSyncManager")

        # Initial sync for all platforms
        for platform in self.config.source_paths:
            await self.sync_to_cache(platform)

        # Start file watchers
        for platform in self.config.source_paths:
            await self._start_watcher(platform)

    async def stop(self) -> None:
        """Stop the sync manager and all file watchers."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping CookieSyncManager")

        # Cancel all watcher tasks
        for platform, task in self.file_watchers.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.file_watchers.clear()

    async def sync_to_cache(self, platform: str) -> SyncResult:
        """Sync cookies from source to daemon cache."""
        source_path = self.config.source_paths.get(platform)
        if not source_path:
            return SyncResult(
                success=False,
                source_hash="",
                cache_hash="",
                sync_direction=SyncDirection.SOURCE_TO_CACHE,
                timestamp=datetime.now().isoformat(),
                files_synced=0,
                conflicts_resolved=0,
                error_message=f"No source path configured for platform: {platform}",
            )

        cache_path = self.cache_dir / f"{platform}.json"

        # Read source file
        try:
            source_content = source_path.read_text()
            source_hash = hashlib.sha256(source_content.encode()).hexdigest()
            source_modified = datetime.fromtimestamp(source_path.stat().st_mtime).isoformat()
        except FileNotFoundError:
            logger.warning(f"Source file not found: {source_path}")
            return SyncResult(
                success=False,
                source_hash="",
                cache_hash="",
                sync_direction=SyncDirection.SOURCE_TO_CACHE,
                timestamp=datetime.now().isoformat(),
                files_synced=0,
                conflicts_resolved=0,
                error_message=f"Source file not found: {source_path}",
            )
        except Exception as e:
            logger.error(f"Error reading source file: {e}")
            return SyncResult(
                success=False,
                source_hash="",
                cache_hash="",
                sync_direction=SyncDirection.SOURCE_TO_CACHE,
                timestamp=datetime.now().isoformat(),
                files_synced=0,
                conflicts_resolved=0,
                error_message=str(e),
            )

        # Read cache file (if exists)
        cache_hash = ""
        cache_modified = ""
        if cache_path.exists():
            try:
                cache_content = cache_path.read_text()
                cache_hash = hashlib.sha256(cache_content.encode()).hexdigest()
                cache_modified = datetime.fromtimestamp(cache_path.stat().st_mtime).isoformat()
            except Exception as e:
                logger.error(f"Error reading cache file: {e}")

        # Check if sync is needed
        if source_hash == cache_hash:
            logger.debug(f"No sync needed for {platform} (hashes match)")
            await self._update_sync_state(
                platform,
                SyncStatus.SYNCED,
                source_hash,
                cache_hash,
                source_modified,
                cache_modified,
                SyncDirection.SOURCE_TO_CACHE,
            )
            return SyncResult(
                success=True,
                source_hash=source_hash,
                cache_hash=cache_hash,
                sync_direction=SyncDirection.SOURCE_TO_CACHE,
                timestamp=datetime.now().isoformat(),
                files_synced=0,
                conflicts_resolved=0,
            )

        # Perform sync
        try:
            cache_path.write_text(source_content)
            cache_hash = source_hash
            cache_modified = datetime.now().isoformat()

            await self._update_sync_state(
                platform,
                SyncStatus.SYNCED,
                source_hash,
                cache_hash,
                source_modified,
                cache_modified,
                SyncDirection.SOURCE_TO_CACHE,
            )

            logger.info(f"Synced {platform} from source to cache")
            return SyncResult(
                success=True,
                source_hash=source_hash,
                cache_hash=cache_hash,
                sync_direction=SyncDirection.SOURCE_TO_CACHE,
                timestamp=datetime.now().isoformat(),
                files_synced=1,
                conflicts_resolved=0,
            )
        except Exception as e:
            logger.error(f"Error syncing {platform}: {e}")
            await self._update_sync_state(
                platform,
                SyncStatus.ERROR,
                source_hash,
                cache_hash,
                source_modified,
                cache_modified,
                SyncDirection.SOURCE_TO_CACHE,
            )
            return SyncResult(
                success=False,
                source_hash=source_hash,
                cache_hash=cache_hash,
                sync_direction=SyncDirection.SOURCE_TO_CACHE,
                timestamp=datetime.now().isoformat(),
                files_synced=0,
                conflicts_resolved=0,
                error_message=str(e),
            )

    async def get_sync_state(self, platform: str) -> SyncState | None:
        """Get current sync state for a platform."""
        state_path = self.sync_state_dir / f"{platform}_sync.json"
        if not state_path.exists():
            return None

        try:
            data = json.loads(state_path.read_text())
            return SyncState(
                platform=data["platform"],
                last_sync_time=data["last_sync_time"],
                last_sync_direction=SyncDirection(data["last_sync_direction"]),
                source_modified_time=data["source_modified_time"],
                cache_modified_time=data["cache_modified_time"],
                sync_status=SyncStatus(data["sync_status"]),
                source_hash=data["source_hash"],
                cache_hash=data["cache_hash"],
            )
        except Exception as e:
            logger.error(f"Error reading sync state for {platform}: {e}")
            return None

    async def get_cookies_from_cache(self, platform: str) -> dict[str, str] | None:
        """Get cookies for a platform from the daemon cache."""
        cache_path = self.cache_dir / f"{platform}.json"
        if not cache_path.exists():
            logger.warning(f"No cached cookies found for {platform}")
            return None

        try:
            data = json.loads(cache_path.read_text())
            return data
        except Exception as e:
            logger.error(f"Error reading cached cookies for {platform}: {e}")
            return None

    async def _start_watcher(self, platform: str) -> None:
        """Start file watching for a platform."""
        source_path = self.config.source_paths.get(platform)
        if not source_path or not source_path.parent.exists():
            logger.warning(f"Cannot watch {platform}: source path does not exist")
            return

        async def watch() -> None:
            try:
                async for changes in awatch(source_path.parent):
                    # Check if the cookie file changed
                    for change_type, path in changes:
                        if Path(path) == source_path:
                            logger.info(f"Detected change in {platform} cookies, syncing...")
                            await self.sync_to_cache(platform)
                            break
            except asyncio.CancelledError:
                logger.debug(f"Watcher for {platform} cancelled")
            except Exception as e:
                logger.error(f"Error watching {platform}: {e}")

        self.file_watchers[platform] = asyncio.create_task(watch())
        logger.info(f"Started file watcher for {platform}")

    async def _update_sync_state(
        self,
        platform: str,
        status: SyncStatus,
        source_hash: str,
        cache_hash: str,
        source_modified: str,
        cache_modified: str,
        direction: SyncDirection,
    ) -> None:
        """Update sync state for a platform."""
        state = SyncState(
            platform=platform,
            last_sync_time=datetime.now().isoformat(),
            last_sync_direction=direction,
            source_modified_time=source_modified,
            cache_modified_time=cache_modified,
            sync_status=status,
            source_hash=source_hash,
            cache_hash=cache_hash,
        )

        state_path = self.sync_state_dir / f"{platform}_sync.json"
        try:
            state_path.write_text(
                json.dumps(
                    {
                        "platform": state.platform,
                        "last_sync_time": state.last_sync_time,
                        "last_sync_direction": state.last_sync_direction.value,
                        "source_modified_time": state.source_modified_time,
                        "cache_modified_time": state.cache_modified_time,
                        "sync_status": state.sync_status.value,
                        "source_hash": state.source_hash,
                        "cache_hash": state.cache_hash,
                    },
                    indent=2,
                )
            )
        except Exception as e:
            logger.error(f"Error updating sync state for {platform}: {e}")
