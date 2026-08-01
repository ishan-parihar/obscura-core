"""
Exceptions for ObscuraCookieManager.
"""

from __future__ import annotations


class ObscuraError(Exception):
    """Base exception for ObscuraCookieManager."""
    pass


class CookieStorageError(ObscuraError):
    """Cookie storage operation failed."""
    pass


class BrowserExtractionError(ObscuraError):
    """Browser cookie extraction failed."""
    pass


class CookieValidationError(ObscuraError):
    """Cookie validation failed."""
    pass


class ReLoginRequiredError(ObscuraError):
    """Authentication invalidated, re-login required."""
    pass


class AuthInvalidatedError(ObscuraError):
    """Auth state was invalidated."""
    pass