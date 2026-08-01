"""Obscura Core - Core library for Obscura browser integration with cookie management, daemon service, connection pooling, and plugin system."""

from obscura_core.cookie_manager import (
    ObscuraCookieManager,
    CookieSource,
    CookieValidationResult,
    CookieStorage,
    FileCookieStorage,
    EnvVarCookieStorage,
    BrowserProfileStorage,
    MultiSourceCookieStorage,
    BrowserExtractor,
    BrowserCookie3Extractor,
    BrowserCookieExtractor,
    SubprocessBrowserExtractor,
    ChromiumCookieExtractor,
    RedditCookieExtractor,
    TwitterCookieExtractor,
    InstagramCookieExtractor,
    LinkedInCookieExtractor,
    ObscuraError,
    CookieStorageError,
    BrowserExtractionError,
    CookieValidationError,
    ReLoginRequiredError,
    AuthInvalidatedError,
)

from obscura_core.core import ObscuraDaemon, daemon_context
from obscura_core.core.models import (
    DaemonConfig,
    BrowserRequirements,
    BrowserHandle,
    PluginStatus,
    HookType,
)

from obscura_core.plugin import ObscuraPlugin

__version__ = "0.1.0"

__all__ = [
    # Cookie Manager
    "ObscuraCookieManager",
    "CookieSource",
    "CookieValidationResult",
    "CookieStorage",
    "FileCookieStorage",
    "EnvVarCookieStorage",
    "BrowserProfileStorage",
    "MultiSourceCookieStorage",
    "BrowserExtractor",
    "BrowserCookie3Extractor",
    "BrowserCookieExtractor",
    "SubprocessBrowserExtractor",
    "ChromiumCookieExtractor",
    "RedditCookieExtractor",
    "TwitterCookieExtractor",
    "InstagramCookieExtractor",
    "LinkedInCookieExtractor",
    "ObscuraError",
    "CookieStorageError",
    "BrowserExtractionError",
    "CookieValidationError",
    "ReLoginRequiredError",
    "AuthInvalidatedError",
    # Daemon
    "ObscuraDaemon",
    "daemon_context",
    "DaemonConfig",
    "BrowserRequirements",
    "BrowserHandle",
    "PluginStatus",
    "HookType",
    # Plugin
    "ObscuraPlugin",
]
