"""
Core ObscuraCookieManager implementation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from obscura_core.cookie_managerstorage import CookieStorage
from obscura_core.cookie_managerextractors import BrowserCookieExtractor
from obscura_core.cookie_managerexceptions import CookieValidationError, AuthInvalidatedError, ReLoginRequiredError

logger = logging.getLogger(__name__)


class CookieSource(str, Enum):
    """Source of cookies."""
    FILE = "file"
    BROWSER_PROFILE = "browser_profile"
    ENV_VAR = "env_var"
    BROWSER_EXTRACTION = "browser_extraction"


@dataclass
class CookieValidationResult:
    """Result of cookie validation."""
    valid: bool
    source: CookieSource
    cookies: dict[str, str]
    error: Optional[str] = None
    re_extracted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ObscuraCookieManager:
    """
    Unified cookie manager with automatic refresh and re-login triggering.
    
    Features:
    - Multiple cookie sources with priority order
    - Periodic validation (configurable interval)
    - Auto re-extraction from browser on validation failure
    - Auth invalidation and re-login triggering on persistent failure
    - Thread-safe async operations
    """
    
    def __init__(
        self,
        storage: CookieStorage,
        extractor: BrowserCookieExtractor,
        validator: Callable[[dict[str, str]], bool],
        required_cookies: list[str],
        validation_interval: int = 300,  # 5 minutes default
        max_re_extraction_attempts: int = 3,
        re_extraction_cooldown: int = 60,  # seconds
    ):
        self.storage = storage
        self.extractor = extractor
        self.validator = validator
        self.required_cookies = required_cookies
        self.validation_interval = validation_interval
        self.max_re_extraction_attempts = max_re_extraction_attempts
        self.re_extraction_cooldown = re_extraction_cooldown
        
        self._cached_cookies: Optional[dict[str, str]] = None
        self._cached_source: Optional[CookieSource] = None
        self._last_validation: float = 0
        self._last_re_extraction: float = 0
        self._re_extraction_attempts: int = 0
        self._lock = asyncio.Lock()
        self._invalidation_callback: Optional[Callable[[], None]] = None
    
    def set_invalidation_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to trigger when auth is invalidated (e.g., re-login flow)."""
        self._invalidation_callback = callback
    
    async def get_cookies(self, force_refresh: bool = False) -> CookieValidationResult:
        """
        Get valid cookies, performing validation and re-extraction as needed.
        
        Args:
            force_refresh: Force re-validation even if within interval
            
        Returns:
            CookieValidationResult with valid cookies
            
        Raises:
            ReLoginRequiredError: If auth is invalidated and re-login is required
        """
        async with self._lock:
            now = time.time()
            
            # Check if we need to validate
            if not force_refresh and self._cached_cookies and self._last_validation > 0:
                if now - self._last_validation < self.validation_interval:
                    return CookieValidationResult(
                        valid=True,
                        source=self._cached_source or CookieSource.FILE,
                        cookies=self._cached_cookies,
                        metadata={"cached": True}
                    )
            
            # Try to get cookies from storage
            cookies = await self.storage.load()
            source = CookieSource.FILE
            
            if not cookies:
                # Try env var
                cookies = await self.storage.load_from_env()
                if cookies:
                    source = CookieSource.ENV_VAR
            
            if not cookies:
                # Try browser extraction
                logger.info("No cookies in storage, attempting browser extraction")
                cookies = await self._extract_from_browser()
                if cookies:
                    source = CookieSource.BROWSER_EXTRACTION
                    await self.storage.save(cookies)
            
            if not cookies:
                raise CookieValidationError("No cookies available from any source")
            
            # Validate cookies
            is_valid = await self._validate_cookies(cookies)
            
            if is_valid:
                self._cached_cookies = cookies
                self._cached_source = source
                self._last_validation = now
                self._re_extraction_attempts = 0
                return CookieValidationResult(
                    valid=True,
                    source=source,
                    cookies=cookies,
                    metadata={"cached": False}
                )
            
            # Validation failed - try re-extraction
            logger.warning("Cookie validation failed, attempting re-extraction from browser")
            return await self._handle_validation_failure(now)
    
    async def _validate_cookies(self, cookies: dict[str, str]) -> bool:
        """Validate cookies using the provided validator function."""
        # Check required cookies are present
        for required in self.required_cookies:
            if required not in cookies:
                logger.debug(f"Required cookie missing: {required}")
                return False
        
        try:
            # Run validator in thread pool if it's sync
            if asyncio.iscoroutinefunction(self.validator):
                return await self.validator(cookies)
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.validator, cookies)
        except Exception as e:
            logger.debug(f"Cookie validation error: {e}")
            return False
    
    async def _extract_from_browser(self) -> Optional[dict[str, str]]:
        """Extract cookies from browser."""
        try:
            cookies = await self.extractor.extract(self.extractor.domain, self.required_cookies)
            if cookies:
                logger.info(f"Extracted {len(cookies)} cookies from browser")
            return cookies
        except Exception as e:
            logger.error(f"Browser extraction failed: {e}")
            return None
    
    async def _handle_validation_failure(self, now: float) -> CookieValidationResult:
        """Handle cookie validation failure with re-extraction logic."""
        # Check cooldown
        if now - self._last_re_extraction < self.re_extraction_cooldown:
            logger.debug("Re-extraction cooldown active, waiting...")
            await asyncio.sleep(self.re_extraction_cooldown - (now - self._last_re_extraction))
        
        # Check max attempts
        if self._re_extraction_attempts >= self.max_re_extraction_attempts:
            logger.error(f"Max re-extraction attempts ({self.max_re_extraction_attempts}) reached")
            await self._invalidate_auth()
            raise ReLoginRequiredError(
                f"Cookie validation failed after {self.max_re_extraction_attempts} re-extraction attempts. "
                "Please re-authenticate."
            )
        
        self._re_extraction_attempts += 1
        self._last_re_extraction = time.time()
        
        # Try re-extraction
        fresh_cookies = await self._extract_from_browser()
        if fresh_cookies:
            # Validate fresh cookies
            is_valid = await self._validate_cookies(fresh_cookies)
            if is_valid:
                logger.info("Re-extracted cookies are valid")
                await self.storage.save(fresh_cookies)
                self._cached_cookies = fresh_cookies
                self._cached_source = CookieSource.BROWSER_EXTRACTION
                self._last_validation = time.time()
                self._re_extraction_attempts = 0
                return CookieValidationResult(
                    valid=True,
                    source=CookieSource.BROWSER_EXTRACTION,
                    cookies=fresh_cookies,
                    re_extracted=True,
                    metadata={"re_extraction_attempt": self._re_extraction_attempts}
                )
            else:
                logger.warning("Re-extracted cookies also failed validation")
        
        # If we get here, re-extraction failed
        if self._re_extraction_attempts >= self.max_re_extraction_attempts:
            await self._invalidate_auth()
            raise ReLoginRequiredError(
                f"Cookie validation failed after {self.max_re_extraction_attempts} re-extraction attempts. "
                "Please re-authenticate."
            )
        
        # Return the old cookies with valid=False to indicate failure
        return CookieValidationResult(
            valid=False,
            source=self._cached_source or CookieSource.FILE,
            cookies=self._cached_cookies or {},
            error="Cookie validation failed, re-extraction attempted",
            metadata={"re_extraction_attempt": self._re_extraction_attempts}
        )
    
    async def _invalidate_auth(self) -> None:
        """Invalidate auth state and trigger re-login callback."""
        logger.warning("Invalidating auth state")
        self._cached_cookies = None
        self._cached_source = None
        self._last_validation = 0
        self._re_extraction_attempts = 0
        
        # Clear storage
        await self.storage.clear()
        
        # Trigger callback if set
        if self._invalidation_callback:
            try:
                if asyncio.iscoroutinefunction(self._invalidation_callback):
                    await self._invalidation_callback()
                else:
                    self._invalidation_callback()
            except Exception as e:
                logger.error(f"Invalidation callback failed: {e}")
    
    async def force_re_extraction(self) -> CookieValidationResult:
        """Force re-extraction from browser (e.g., after user logs in)."""
        async with self._lock:
            self._re_extraction_attempts = 0
            self._last_re_extraction = 0
            return await self.get_cookies(force_refresh=True)
    
    async def invalidate_and_trigger_relogin(self) -> None:
        """Manually invalidate auth and trigger re-login."""
        async with self._lock:
            await self._invalidate_auth()
            raise ReLoginRequiredError("Auth invalidated, re-login required")
    
    def get_cached_cookies(self) -> Optional[dict[str, str]]:
        """Get currently cached cookies without validation."""
        return self._cached_cookies
    
    def get_cached_source(self) -> Optional[CookieSource]:
        """Get source of currently cached cookies."""
        return self._cached_source
    
    def is_cache_valid(self) -> bool:
        """Check if cached cookies are within validation interval."""
        if not self._cached_cookies or self._last_validation == 0:
            return False
        return time.time() - self._last_validation < self.validation_interval