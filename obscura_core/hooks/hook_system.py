"""Hook system for extensibility."""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Callable

from loguru import logger

from obscura_core.core.models import Hook, HookType


class HookSystem:
    """Manages hook registration and triggering."""

    def __init__(self) -> None:
        self._hooks: dict[HookType, list[Hook]] = defaultdict(list)
        self._callbacks: dict[str, Callable] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        hook_type: HookType,
        callback: Callable,
        priority: int = 0,
        platform: str | None = None,
    ) -> str:
        """Register a hook callback."""
        callback_id = str(uuid.uuid4())

        hook = Hook(
            hook_type=hook_type,
            callback_id=callback_id,
            priority=priority,
            platform=platform,
        )

        async with self._lock:
            self._hooks[hook_type].append(hook)
            self._callbacks[callback_id] = callback
            # Sort by priority (higher priority first)
            self._hooks[hook_type].sort(key=lambda h: h.priority, reverse=True)

        logger.info(f"Registered hook {callback_id} for {hook_type.value}")
        return callback_id

    async def unregister(self, callback_id: str) -> bool:
        """Unregister a hook callback."""
        async with self._lock:
            if callback_id not in self._callbacks:
                logger.warning(f"Hook {callback_id} not found")
                return False

            del self._callbacks[callback_id]

            # Remove from all hook type lists
            for hook_type, hooks in self._hooks.items():
                self._hooks[hook_type] = [h for h in hooks if h.callback_id != callback_id]

            logger.info(f"Unregistered hook {callback_id}")
            return True

    async def trigger(self, hook_type: HookType, context: dict) -> None:
        """Trigger all hooks of a given type."""
        async with self._lock:
            hooks = self._hooks[hook_type].copy()

        if not hooks:
            return

        logger.debug(f"Triggering {len(hooks)} hooks for {hook_type.value}")

        # Execute hooks in priority order
        for hook in hooks:
            callback = self._callbacks.get(hook.callback_id)
            if not callback:
                continue

            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(context)
                else:
                    callback(context)
            except Exception as e:
                logger.error(f"Error in hook {hook.callback_id}: {e}")

    async def get_hooks(self, hook_type: HookType | None = None) -> list[Hook]:
        """Get registered hooks, optionally filtered by type."""
        async with self._lock:
            if hook_type:
                return self._hooks[hook_type].copy()
            else:
                all_hooks = []
                for hooks in self._hooks.values():
                    all_hooks.extend(hooks)
                return all_hooks
