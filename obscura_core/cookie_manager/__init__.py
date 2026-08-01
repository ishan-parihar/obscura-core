"""
ObscuraCookieManager - Shared cookie refresh mechanism for CLI tools.

Provides:
- Automatic cookie validation and refresh
- Browser cookie extraction with fallback strategies
- Multi-source cookie storage (file, env var, browser profile)
- Platform-specific extractors for Reddit, Twitter, Instagram
"""

from __future__ import annotations

from obscura_core.cookie_manager..core import ObscuraCookieManager, CookieSource, CookieValidationResult
from obscura_core.cookie_manager..storage import (
    CookieStorage,
    FileCookieStorage,
    EnvVarCookieStorage,
    BrowserProfileStorage,
    MultiSourceCookieStorage,
)
from obscura_core.cookie_manager..browser_extraction import (
    BrowserExtractor,
    BrowserCookie3Extractor,
    SubprocessBrowserExtractor,
    ChromiumCookieExtractor,
)
from obscura_core.cookie_manager..extractors import (
    BrowserCookieExtractor,
    RedditCookieExtractor,
    TwitterCookieExtractor,
    InstagramCookieExtractor,
    LinkedInCookieExtractor,
)
from obscura_core.cookie_manager..exceptions import (
    ObscuraError,
    CookieStorageError,
    BrowserExtractionError,
    CookieValidationError,
    ReLoginRequiredError,
    AuthInvalidatedError,
)

__version__ = "0.1.0"

__all__ = [
    # Manager
    "ObscuraCookieManager",
    "CookieSource",
    "CookieValidationResult",
    # Storage
    "CookieStorage",
    "FileCookieStorage",
    "EnvVarCookieStorage",
    "BrowserProfileStorage",
    "MultiSourceCookieStorage",
    # Browser extraction
    "BrowserExtractor",
    "BrowserCookie3Extractor",
    "BrowserCookieExtractor",
    "SubprocessBrowserExtractor",
    "ChromiumCookieExtractor",
    # Platform-specific extractors
    "RedditCookieExtractor",
    "TwitterCookieExtractor",
    "InstagramCookieExtractor",
    "LinkedInCookieExtractor",
    # Exceptions
    "ObscuraError",
    "CookieStorageError",
    "BrowserExtractionError",
    "CookieValidationError",
    "ReLoginRequiredError",
    "AuthInvalidatedError",
]