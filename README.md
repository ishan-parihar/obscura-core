# Obscura Core

Core library for Obscura browser integration with cookie management, daemon service, connection pooling, and plugin system.

## Overview

Obscura Core provides a unified library for managing browser automation, cookie synchronization, and daemon services across multiple CLI tools (linkedin-lyr, instagram-lyr, reddit-lyr, twitter-lyr).

## Features

### Cookie Management
- **Automatic Cookie Validation**: Periodically validates cookies against platform APIs
- **Browser Cookie Extraction**: Automatically extracts cookies from browsers (Chrome, Firefox, Brave, Arc, etc.)
- **Multi-Source Storage**: Supports file storage, environment variables, and browser profiles
- **Auth Invalidation**: Triggers re-login flows when cookies are persistently invalid
- **Platform-Specific Extractors**: Pre-configured extractors for Reddit, Twitter/X, Instagram, LinkedIn

### Daemon Service
- **Cookie Synchronization**: Automatically syncs cookies from tool-specific locations to a centralized cache
- **Connection Pooling**: Manages browser connection pools with dynamic port allocation
- **Hook System**: Extensible hook system for custom behavior
- **Runtime Detection**: Shared runtime detection for consistent profile management
- **HTTP API**: REST API for tool integration

## Installation

```bash
pip install obscura-core
```

Or with uv:

```bash
uv add obscura-core
```

## Usage

### Cookie Manager Only

```python
import asyncio
from obscura_core import (
    ObscuraCookieManager,
    FileCookieStorage,
    TwitterCookieExtractor,
    CookieSource,
)

async def main():
    # Define your cookie validator
    def validator(cookies: dict[str, str]) -> bool:
        return "auth_token" in cookies

    # Create manager
    storage = FileCookieStorage("/path/to/cookies.json")
    extractor = TwitterCookieExtractor()

    manager = ObscuraCookieManager(
        storage=storage,
        extractor=extractor,
        validator=validator,
        required_cookies=["auth_token", "ct0"],
        validation_interval=300,  # 5 minutes
    )

    # Get valid cookies
    result = await manager.get_cookies()

    if result.valid:
        print(f"Valid cookies from {result.source}")
        print(f"Cookies: {result.cookies}")
    else:
        print(f"Invalid cookies: {result.error}")

asyncio.run(main())
```

### Daemon Service

```bash
# Start the daemon
obscura-daemon
```

The daemon will start on `http://127.0.0.1:9999` by default.

### Using the Plugin Client

```python
from obscura_core import ObscuraPlugin, BrowserRequirements

async with ObscuraPlugin() as plugin:
    # Get cookies
    cookies = await plugin.get_cookies("linkedin")

    # Acquire browser
    requirements = BrowserRequirements(platform="linkedin", headless=True)
    browser = await plugin.acquire_browser("linkedin", requirements)

    # Release browser
    await plugin.release_browser(browser.browser_id)

    # Get status
    status = await plugin.get_status()
```

## Configuration

### Cookie Manager Configuration

```python
from obscura_core import ObscuraCookieManager

manager = ObscuraCookieManager(
    storage=storage,
    extractor=extractor,
    validator=validator,
    required_cookies=["sessionid"],
    validation_interval=600,  # 10 minutes
    max_re_extraction_attempts=3,
    re_extraction_cooldown=60,  # seconds
)
```

### Daemon Configuration

```python
from obscura_core import DaemonConfig

config = DaemonConfig(
    host="127.0.0.1",
    port=9999,
    max_connections=10,
    connection_idle_timeout=300,
    sync_interval=5,
)
```

## Storage Structure

```
~/.obscura/
├── config/
│   ├── daemon.json
│   ├── platforms.json
│   └── hooks.json
├── cache/
│   ├── cookies/
│   │   ├── linkedin.json
│   │   ├── instagram.json
│   │   ├── reddit.json
│   │   └── twitter.json
│   ├── connection_pool/
│   └── sync_state/
├── logs/
│   └── daemon.log
└── obscura-daemon.pid
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/v1/status` - Get daemon status
- `POST /api/v1/browser/acquire` - Acquire browser from pool
- `POST /api/v1/browser/release` - Release browser back to pool
- `GET /api/v1/cookies/{platform}` - Get cookies for platform
- `POST /api/v1/sync/{platform}` - Trigger cookie sync
- `POST /api/v1/hooks/register` - Register hook
- `POST /api/v1/hooks/unregister` - Unregister hook

## Development

```bash
# Clone repository
git clone https://github.com/ishan-parihar/obscura-core.git
cd obscura-core

# Install in development mode
uv sync

# Install dev dependencies
uv sync --extra dev

# Run linting
uv run ruff check .

# Run type checking
uv run mypy .

# Run tests
uv run pytest
```

## License

MIT
