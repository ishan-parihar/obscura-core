# Obscura Daemon

Centralized daemon for Obscura browser integration with cookie sync, connection pooling, and plugin system.

## Overview

Obscura Daemon provides a unified service for managing browser automation and cookie synchronization across multiple CLI tools (linkedin-lyr, instagram-lyr, reddit-lyr, twitter-lyr).

## Features

- **Cookie Synchronization**: Automatically syncs cookies from tool-specific locations to a centralized cache
- **Connection Pooling**: Manages browser connection pools with dynamic port allocation
- **Hook System**: Extensible hook system for custom behavior
- **Runtime Detection**: Shared runtime detection for consistent profile management
- **HTTP API**: REST API for tool integration

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Obscura Daemon                           │
├─────────────────────────────────────────────────────────────┤
│  Cookie Sync Layer  │  Connection Pool  │  Hook System      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ LinkedIn CLI │ Instagram    │ Reddit HTTPX │ Twitter CLI  │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

## Installation

```bash
cd obscura-daemon
uv sync
```

## Usage

### Start the daemon

```bash
uv run obscura-daemon
```

The daemon will start on `http://127.0.0.1:9999` by default.

### Using the plugin client

```python
from obscura_daemon.plugin.client import ObscuraPlugin
from obscura_daemon.core.models import BrowserRequirements

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

Configuration is managed via `DaemonConfig` class:

```python
from obscura_daemon.core.models import DaemonConfig

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
# Install dev dependencies
uv sync --extra dev

# Run linting
uv run ruff check .

# Run type checking
uv run ty check

# Run tests
uv run pytest
```

## License

MIT
