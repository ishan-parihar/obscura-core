"""
Cookie storage backends for ObscuraCookieManager.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from obscura_core.cookie_manager.exceptions import CookieStorageError


class CookieStorage(ABC):
    """Abstract base class for cookie storage."""
    
    @abstractmethod
    async def load(self) -> Optional[dict[str, str]]:
        """Load cookies from storage."""
        pass
    
    @abstractmethod
    async def save(self, cookies: dict[str, str]) -> None:
        """Save cookies to storage."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear stored cookies."""
        pass
    
    async def load_from_env(self) -> Optional[dict[str, str]]:
        """Load cookies from environment variable (optional)."""
        return None


class FileCookieStorage(CookieStorage):
    """Store cookies in a JSON file."""
    
    def __init__(self, file_path: Path, env_var: Optional[str] = None):
        self.file_path = file_path
        self.env_var = env_var
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def load(self) -> Optional[dict[str, str]]:
        if not self.file_path.exists():
            return None
        try:
            data = json.loads(self.file_path.read_text())
            # Support both {"cookies": {...}} and {...} formats
            if isinstance(data, dict):
                return data.get("cookies", data)
            return None
        except (json.JSONDecodeError, OSError) as e:
            raise CookieStorageError(f"Failed to load cookies from {self.file_path}: {e}")
    
    async def save(self, cookies: dict[str, str]) -> None:
        try:
            data = {"cookies": cookies}
            self.file_path.write_text(json.dumps(data, indent=2))
            self.file_path.chmod(0o600)
        except OSError as e:
            raise CookieStorageError(f"Failed to save cookies to {self.file_path}: {e}")
    
    async def clear(self) -> None:
        if self.file_path.exists():
            try:
                self.file_path.unlink()
            except OSError as e:
                raise CookieStorageError(f"Failed to clear cookies: {e}")
    
    async def load_from_env(self) -> Optional[dict[str, str]]:
        if not self.env_var:
            return None
        raw = os.environ.get(self.env_var)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k and v}
            elif isinstance(data, list):
                return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
        except json.JSONDecodeError:
            pass
        return None


class EnvVarCookieStorage(CookieStorage):
    """Store cookies in environment variable (for headless environments)."""
    
    def __init__(self, env_var: str):
        self.env_var = env_var
    
    async def load(self) -> Optional[dict[str, str]]:
        raw = os.environ.get(self.env_var)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if k and v}
            elif isinstance(data, list):
                return {c["name"]: c["value"] for c in data if "name" in c and "value" in c}
        except json.JSONDecodeError:
            pass
        return None
    
    async def save(self, cookies: dict[str, str]) -> None:
        # Can't actually save to env var in current process
        # This is mainly for loading
        pass
    
    async def clear(self) -> None:
        pass


class BrowserProfileStorage(CookieStorage):
    """Store cookies in a browser profile directory (for persistent browser sessions)."""
    
    def __init__(self, profile_dir: Path):
        self.profile_dir = profile_dir
        self.cookies_file = profile_dir / "cookies.json"
        self.state_file = profile_dir / "source-state.json"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
    
    async def load(self) -> Optional[dict[str, str]]:
        if not self.cookies_file.exists():
            return None
        try:
            data = json.loads(self.cookies_file.read_text())
            if isinstance(data, dict):
                cookies = data.get("cookies", data)
                # Profile format stores cookies as a list of {name, value, ...}
                if isinstance(cookies, list):
                    return {
                        c["name"]: c["value"]
                        for c in cookies
                        if isinstance(c, dict) and "name" in c and "value" in c
                    }
                if isinstance(cookies, dict):
                    return cookies
            return None
        except (json.JSONDecodeError, OSError) as e:
            raise CookieStorageError(f"Failed to load cookies from {self.cookies_file}: {e}")
    
    async def save(self, cookies: dict[str, str]) -> None:
        try:
            data = {
                "cookies": [
                    {
                        "name": name,
                        "value": value,
                        "domain": ".reddit.com",  # Default, should be configurable
                        "path": "/",
                        "secure": True,
                        "expires": -1,
                    }
                    for name, value in cookies.items()
                ],
                "imported_from": "browser_profile",
            }
            self.cookies_file.write_text(json.dumps(data, indent=2))
            self.cookies_file.chmod(0o600)
        except OSError as e:
            raise CookieStorageError(f"Failed to save cookies to {self.cookies_file}: {e}")
    
    async def clear(self) -> None:
        for f in [self.cookies_file, self.state_file]:
            if f.exists():
                try:
                    f.unlink()
                except OSError:
                    pass
    
    def get_state_path(self) -> Path:
        return self.state_file
    
    def profile_exists(self) -> bool:
        return self.profile_dir.exists()


class MultiSourceCookieStorage(CookieStorage):
    """Try multiple storage sources in priority order."""
    
    def __init__(self, sources: list[CookieStorage]):
        self.sources = sources
    
    async def load(self) -> Optional[dict[str, str]]:
        for source in self.sources:
            cookies = await source.load()
            if cookies:
                return cookies
        return None
    
    async def save(self, cookies: dict[str, str]) -> None:
        # Save to all sources
        for source in self.sources:
            try:
                await source.save(cookies)
            except Exception:
                pass  # Best effort
    
    async def clear(self) -> None:
        for source in self.sources:
            try:
                await source.clear()
            except Exception:
                pass
    
    async def load_from_env(self) -> Optional[dict[str, str]]:
        for source in self.sources:
            cookies = await source.load_from_env()
            if cookies:
                return cookies
        return None