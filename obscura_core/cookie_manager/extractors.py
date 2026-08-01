"""
Platform-specific cookie extractors for Reddit, Twitter, Instagram.
"""

from __future__ import annotations

from typing import Optional

from obscura_core.cookie_managerbrowser_extraction import BrowserExtractorFactory


class BrowserCookieExtractor:
    """Base browser cookie extractor interface."""
    
    def __init__(self, domain: str, required_cookies: list[str], preferred_browsers: Optional[list[str]] = None):
        self.domain = domain
        self.required_cookies = required_cookies
        self.preferred_browsers = preferred_browsers or []
    
    async def extract(self, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        """Extract cookies from any available browser."""
        return await BrowserExtractorFactory.extract_from_any(
            domain,
            required_cookies,
            self.preferred_browsers
        )


class RedditCookieExtractor(BrowserCookieExtractor):
    """Extract Reddit cookies (token_v2, reddit_session, csrf_token)."""
    
    def __init__(self, preferred_browsers: Optional[list[str]] = None):
        super().__init__(
            domain="reddit.com",
            required_cookies=["token_v2", "reddit_session"],
            preferred_browsers=preferred_browsers or ["zen", "brave", "chrome", "firefox", "edge"]
        )


class TwitterCookieExtractor(BrowserCookieExtractor):
    """Extract Twitter/X cookies (auth_token, ct0)."""
    
    def __init__(self, preferred_browsers: Optional[list[str]] = None):
        super().__init__(
            domain="x.com",
            required_cookies=["auth_token", "ct0"],
            preferred_browsers=preferred_browsers or ["arc", "chrome", "edge", "firefox", "brave"]
        )


class InstagramCookieExtractor(BrowserCookieExtractor):
    """Extract Instagram cookies (sessionid, csrftoken)."""
    
    def __init__(self, preferred_browsers: Optional[list[str]] = None):
        super().__init__(
            domain="instagram.com",
            required_cookies=["sessionid", "csrftoken"],
            preferred_browsers=preferred_browsers or ["chrome", "brave", "firefox", "edge"]
        )


class LinkedInCookieExtractor(BrowserCookieExtractor):
    """Extract LinkedIn cookies (li_at, JSESSIONID)."""
    
    def __init__(self, preferred_browsers: Optional[list[str]] = None):
        super().__init__(
            domain="linkedin.com",
            required_cookies=["li_at"],
            preferred_browsers=preferred_browsers or ["chrome", "brave", "firefox", "edge"]
        )


# Convenience functions
async def extract_reddit_cookies(preferred_browsers: Optional[list[str]] = None) -> Optional[dict[str, str]]:
    """Extract Reddit cookies from browser."""
    extractor = RedditCookieExtractor(preferred_browsers)
    return await extractor.extract(extractor.domain, extractor.required_cookies)


async def extract_twitter_cookies(preferred_browsers: Optional[list[str]] = None) -> Optional[dict[str, str]]:
    """Extract Twitter/X cookies from browser."""
    extractor = TwitterCookieExtractor(preferred_browsers)
    return await extractor.extract(extractor.domain, extractor.required_cookies)


async def extract_instagram_cookies(preferred_browsers: Optional[list[str]] = None) -> Optional[dict[str, str]]:
    """Extract Instagram cookies from browser."""
    extractor = InstagramCookieExtractor(preferred_browsers)
    return await extractor.extract(extractor.domain, extractor.required_cookies)


async def extract_linkedin_cookies(preferred_browsers: Optional[list[str]] = None) -> Optional[dict[str, str]]:
    """Extract LinkedIn cookies from browser."""
    extractor = LinkedInCookieExtractor(preferred_browsers)
    return await extractor.extract(extractor.domain, extractor.required_cookies)