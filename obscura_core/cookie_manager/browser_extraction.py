"""
Browser cookie extraction for ObscuraCookieManager.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from obscura_core.cookie_managerexceptions import BrowserExtractionError

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """Configuration for a browser."""
    name: str
    cookie_file_paths: list[Path]
    is_chromium: bool = True
    profile_detection: bool = True


class BrowserExtractor(ABC):
    """Abstract base class for browser cookie extractors."""
    
    @abstractmethod
    async def extract(self, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        """Extract cookies for a domain."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this browser is available."""
        pass


class BrowserCookie3Extractor(BrowserExtractor):
    """Extract cookies using browser_cookie3 library."""
    
    def __init__(self, browser_name: str, cookie_file: Optional[Path] = None):
        self.browser_name = browser_name
        self.cookie_file = cookie_file
        self.name = browser_name  # For priority sorting
        self._browser_fn = None
    
    def _get_browser_fn(self):
        """Get the browser_cookie3 function for this browser."""
        if self._browser_fn is not None:
            return self._browser_fn
        
        try:
            import browser_cookie3
            browser_fns = {
                "chrome": browser_cookie3.chrome,
                "arc": browser_cookie3.arc,
                "edge": browser_cookie3.edge,
                "firefox": browser_cookie3.firefox,
                "brave": browser_cookie3.brave,
                "zen": browser_cookie3.firefox,  # Zen uses Firefox format
            }
            self._browser_fn = browser_fns.get(self.browser_name)
            return self._browser_fn
        except ImportError:
            return None
    
    def is_available(self) -> bool:
        return self._get_browser_fn() is not None
    
    async def extract(self, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        fn = self._get_browser_fn()
        if not fn:
            return None
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            if self.cookie_file:
                jar = await loop.run_in_executor(None, lambda: fn(cookie_file=str(self.cookie_file), domain_name=domain))
            else:
                jar = await loop.run_in_executor(None, lambda: fn(domain_name=domain))
            
            return self._extract_from_jar(jar, domain, required_cookies)
        except Exception as e:
            logger.debug(f"{self.browser_name} extraction failed: {e}")
            return None
    
    def _extract_from_jar(self, jar: Any, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        result = {}
        all_cookies = {}
        
        for cookie in jar:
            cookie_domain = cookie.domain or ""
            if domain in cookie_domain or cookie_domain.endswith("." + domain):
                if cookie.name in required_cookies:
                    result[cookie.name] = cookie.value
                if cookie.name and cookie.value:
                    all_cookies[cookie.name] = cookie.value
        
        if all(k in result for k in required_cookies):
            result["_all_cookies"] = all_cookies
            return result
        return None


class SubprocessBrowserExtractor(BrowserExtractor):
    """Extract cookies via subprocess (fallback for SQLite locks)."""
    
    def __init__(self, browser_name: str, cookie_file: Optional[Path] = None):
        self.browser_name = browser_name
        self.cookie_file = cookie_file
        self.name = browser_name  # For priority sorting
    
    def is_available(self) -> bool:
        return True  # Always available if python is available
    
    async def extract(self, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        script = self._build_extraction_script(domain, required_cookies, self.browser_name)
        
        try:
            # Try current environment first
            result = await self._run_extraction(script, "current")
            if result:
                return result
            
            # Try with uv fallback
            result = await self._run_extraction(script, "uv")
            return result
        except Exception as e:
            logger.debug(f"Subprocess extraction failed: {e}")
            return None
    
    def _build_extraction_script(self, domain: str, required_cookies: list[str], browser_name: str) -> str:
        required_json = json.dumps(required_cookies)
        return f'''
import json, os, sys, glob
try:
    import browser_cookie3
except ImportError:
    print(json.dumps({{"error": "browser-cookie3 not installed"}}))
    sys.exit(1)

CHROMIUM_BASE_DIRS = {{
    "chrome": os.path.join("Google", "Chrome"),
    "arc": os.path.join("Arc", "User Data"),
    "edge": os.path.join("Microsoft Edge"),
    "brave": os.path.join("BraveSoftware", "Brave-Browser"),
}}

def iter_cookie_files(browser_name):
    base_dir = CHROMIUM_BASE_DIRS.get(browser_name)
    if base_dir is None:
        return []
    if sys.platform == "darwin":
        root = os.path.join(os.path.expanduser("~"), "Library", "Application Support", base_dir)
    elif sys.platform == "win32":
        if browser_name == "edge":
            root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data")
        else:
            root = os.path.join(os.environ.get("LOCALAPPDATA", ""), base_dir)
    else:
        if browser_name == "edge":
            root = os.path.join(os.path.expanduser("~"), ".config", "microsoft-edge")
        else:
            root = os.path.join(os.path.expanduser("~"), ".config", base_dir)
    if not os.path.isdir(root):
        return []
    env_profile = os.environ.get("TWITTER_CHROME_PROFILE", "").strip()
    if env_profile:
        p = os.path.join(root, env_profile, "Cookies")
        return [p] if os.path.exists(p) else []
    paths = []
    d = os.path.join(root, "Default", "Cookies")
    if os.path.exists(d):
        paths.append(d)
    for pd in sorted(glob.glob(os.path.join(root, "Profile *"))):
        cf = os.path.join(pd, "Cookies")
        if os.path.exists(cf):
            paths.append(cf)
    return paths

def extract_from_jar(jar, name, profile=""):
    result = {{}}
    all_cookies = {{}}
    for cookie in jar:
        domain = cookie.domain or ""
        if "{domain}" in domain or domain.endswith("." + "{domain}"):
            if cookie.name in {required_json}:
                result[cookie.name] = cookie.value
            if cookie.name and cookie.value:
                all_cookies[cookie.name] = cookie.value
    if all(k in result for k in {required_json}):
        result["_all_cookies"] = all_cookies
        return result
    return None

browser_fns = {{
    "arc": browser_cookie3.arc,
    "chrome": browser_cookie3.chrome,
    "edge": browser_cookie3.edge,
    "firefox": browser_cookie3.firefox,
    "brave": browser_cookie3.brave,
}}

fn = browser_fns.get("{browser_name}")
if not fn:
    print(json.dumps({{"error": "Unknown browser"}}))
    sys.exit(1)

if "{browser_name}" in CHROMIUM_BASE_DIRS:
    cookie_files = iter_cookie_files("{browser_name}")
    if not cookie_files:
        try:
            jar = fn()
        except Exception as exc:
            print(json.dumps({{"error": str(exc)}}))
            sys.exit(1)
        r = extract_from_jar(jar, "{browser_name}")
        if r:
            print(json.dumps(r))
            sys.exit(0)
    for cf in cookie_files:
        pname = os.path.basename(os.path.dirname(cf))
        try:
            jar = fn(cookie_file=cf)
        except Exception as exc:
            continue
        r = extract_from_jar(jar, "{browser_name}", pname)
        if r:
            print(json.dumps(r))
            sys.exit(0)
else:
    try:
        jar = fn()
    except Exception as exc:
        print(json.dumps({{"error": str(exc)}}))
        sys.exit(1)
    r = extract_from_jar(jar, "{browser_name}")
    if r:
        print(json.dumps(r))
        sys.exit(0)

print(json.dumps({{"error": "No cookies found"}}))
sys.exit(1)
'''
    
    async def _run_extraction(self, script: str, label: str) -> Optional[dict[str, str]]:
        if label == "current":
            cmd = [sys.executable, "-c", script]
        else:
            cmd = ["uv", "run", "--with", "browser-cookie3", "python", "-c", script]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            
            if proc.returncode != 0:
                logger.debug(f"Subprocess extraction ({label}) failed: {stderr.decode()}")
                return None
            
            output = stdout.decode().strip()
            if not output:
                return None
            
            data = json.loads(output)
            if "error" in data:
                logger.debug(f"Subprocess extraction ({label}) error: {data.get('error')}")
                return None
            
            return data
        except (asyncio.TimeoutError, json.JSONDecodeError, Exception) as e:
            logger.debug(f"Subprocess extraction ({label}) failed: {e}")
            return None


class ChromiumCookieExtractor(BrowserExtractor):
    """Extract cookies from Chromium-based browsers using direct SQLite access."""
    
    def __init__(self, browser_name: str, cookie_file: Path):
        self.browser_name = browser_name
        self.cookie_file = cookie_file
        self.name = browser_name  # For priority sorting
    
    def is_available(self) -> bool:
        return self.cookie_file.exists()
    
    async def extract(self, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        if not self.cookie_file.exists():
            return None
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._extract_sync, domain, required_cookies
            )
        except Exception as e:
            logger.debug(f"Chromium extraction failed: {e}")
            return None
    
    def _extract_sync(self, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        import sqlite3
        
        # Copy to temp file to avoid locks
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        shutil.copy2(self.cookie_file, tmp.name)
        
        try:
            conn = sqlite3.connect(tmp.name)
            cursor = conn.execute(
                "SELECT name, value, encrypted_value FROM cookies WHERE host_key LIKE ?",
                (f"%{domain}%",)
            )
            
            cookies = {}
            all_cookies = {}
            key = self._get_chromium_key()
            
            for name, value, encrypted_value in cursor.fetchall():
                if value:
                    cookies[name] = value
                elif encrypted_value and key:
                    decrypted = self._decrypt_chromium_value(encrypted_value, key)
                    if decrypted:
                        cookies[name] = decrypted
                
                if name and (value or (encrypted_value and key)):
                    all_cookies[name] = cookies.get(name, "")
            
            conn.close()
            
            if all(k in cookies for k in required_cookies):
                cookies["_all_cookies"] = all_cookies
                return cookies
            return None
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
    
    def _get_chromium_key(self) -> Optional[bytes]:
        """Get the decryption key for Chromium cookies on Linux."""
        try:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA1(), length=16, salt=b"saltysalt", iterations=1
            )
            return kdf.derive(b"peanuts")
        except Exception:
            return None
    
    def _decrypt_chromium_value(self, encrypted_value: bytes, key: bytes) -> str:
        """Decrypt a Chromium encrypted cookie value."""
        if not encrypted_value:
            return ""
        if encrypted_value[:3] in (b"v10", b"v11"):
            encrypted_value = encrypted_value[3:]
            try:
                from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                
                iv = b" " * 16
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                decryptor = cipher.decryptor()
                decrypted = decryptor.update(encrypted_value) + decryptor.finalize()
                
                # Remove PKCS7 padding
                pad_len = decrypted[-1]
                if isinstance(pad_len, int) and 1 <= pad_len <= 16:
                    decrypted = decrypted[:-pad_len]
                
                # Skip first 32 bytes (random salt)
                if len(decrypted) > 32:
                    return decrypted[32:].decode("utf-8", errors="ignore")
                return decrypted.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return ""


class FirefoxCookieExtractor(BrowserExtractor):
    """Extract cookies from Firefox/Zen browsers using direct SQLite access."""
    
    def __init__(self, cookie_file: Path, browser_name: str = "firefox"):
        self.cookie_file = cookie_file
        self.name = browser_name  # For priority sorting
    
    def is_available(self) -> bool:
        return self.cookie_file.exists()
    
    async def extract(self, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        if not self.cookie_file.exists():
            return None
        
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._extract_sync, domain, required_cookies
            )
        except Exception as e:
            logger.debug(f"Firefox extraction failed: {e}")
            return None
    
    def _extract_sync(self, domain: str, required_cookies: list[str]) -> Optional[dict[str, str]]:
        import sqlite3
        
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        shutil.copy2(self.cookie_file, tmp.name)
        
        try:
            conn = sqlite3.connect(tmp.name)
            cursor = conn.execute("PRAGMA table_info(moz_cookies)")
            columns = {row[1] for row in cursor.fetchall()}
            domain_col = "host" if "host" in columns else "baseDomain"
            
            cursor = conn.execute(
                f"SELECT name, value FROM moz_cookies WHERE {domain_col} LIKE ? AND value != ''",
                (f"%{domain}%",)
            )
            
            cookies = {}
            for name, value in cursor.fetchall():
                cookies[name] = value
            
            conn.close()
            
            if all(k in cookies for k in required_cookies):
                cookies["_all_cookies"] = cookies.copy()
                return cookies
            return None
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


class BrowserExtractorFactory:
    """Factory for creating browser extractors."""
    
    @staticmethod
    def create_all(domain: str, required_cookies: list[str]) -> list[BrowserExtractor]:
        """Create all available extractors for the current platform."""
        extractors = []
        platform = "darwin" if sys.platform == "darwin" else "linux"
        
        # Chromium-based browsers
        chromium_browsers = {
            "chrome": {
                "linux": Path.home() / ".config/google-chrome/Default/Cookies",
                "darwin": Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
            },
            "brave": {
                "linux": Path.home() / ".config/BraveSoftware/Brave-Browser/Default/Cookies",
                "darwin": Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies",
            },
            "brave-origin-beta": {
                "linux": Path.home() / ".config/BraveSoftware/Brave-Origin-Beta/Default/Cookies",
                "darwin": Path.home() / "Library/Application Support/BraveSoftware/Brave-Origin-Beta/Default/Cookies",
            },
            "edge": {
                "linux": Path.home() / ".config/microsoft-edge/Default/Cookies",
                "darwin": Path.home() / "Library/Application Support/Microsoft Edge/Default/Cookies",
            },
        }
        
        for browser, paths in chromium_browsers.items():
            cookie_file = paths.get(platform)
            if cookie_file and cookie_file.exists():
                extractors.append(ChromiumCookieExtractor(browser, cookie_file))
                extractors.append(BrowserCookie3Extractor(browser, cookie_file))
                extractors.append(SubprocessBrowserExtractor(browser, cookie_file))
        
        # Firefox
        firefox_base = {
            "linux": Path.home() / ".mozilla/firefox",
            "darwin": Path.home() / "Library/Application Support/Firefox/Profiles",
        }.get(platform)
        
        if firefox_base and firefox_base.exists():
            for profile_dir in firefox_base.iterdir():
                cookies_file = profile_dir / "cookies.sqlite"
                if cookies_file.exists():
                    extractors.append(FirefoxCookieExtractor(cookies_file, "firefox"))
                    extractors.append(BrowserCookie3Extractor("firefox", cookies_file))
                    extractors.append(SubprocessBrowserExtractor("firefox", cookies_file))
                    break
        
        # Zen browser
        zen_base = {
            "linux": Path.home() / ".zen",
            "darwin": Path.home() / "Library/Application Support/Zen",
        }.get(platform)
        
        if zen_base and zen_base.exists():
            for profile_dir in zen_base.iterdir():
                if profile_dir.is_dir():
                    cookies_file = profile_dir / "cookies.sqlite"
                    if cookies_file.exists():
                        extractors.append(FirefoxCookieExtractor(cookies_file, "zen"))
                        extractors.append(BrowserCookie3Extractor("zen", cookies_file))
                        extractors.append(SubprocessBrowserExtractor("zen", cookies_file))
                        break
        
        return extractors
    
    @staticmethod
    async def extract_from_any(
        domain: str, 
        required_cookies: list[str],
        preferred_browsers: Optional[list[str]] = None
    ) -> Optional[dict[str, str]]:
        """Try all available extractors until one succeeds."""
        extractors = BrowserExtractorFactory.create_all(domain, required_cookies)
        
        # Sort by preference
        if preferred_browsers:
            def priority(e):
                browser_name = getattr(e, 'name', None)
                if browser_name:
                    for i, b in enumerate(preferred_browsers):
                        if b in browser_name:
                            return i
                return 999
            extractors.sort(key=priority)
        
        for extractor in extractors:
            if not extractor.is_available():
                continue
            try:
                result = await extractor.extract(domain, required_cookies)
                if result:
                    logger.info(f"Extracted cookies from {extractor.__class__.__name__}")
                    return result
            except Exception as e:
                logger.debug(f"Extractor {extractor.__class__.__name__} failed: {e}")
                continue
        
        return None