"""Main entry point for Obscura daemon."""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

import uvicorn
from loguru import logger

from obscura_core.core.daemon import ObscuraDaemon
from obscura_core.core.models import DaemonConfig
from obscura_core.core.server import create_app


def main() -> None:
    """Main entry point."""
    # Load configuration
    config = DaemonConfig()

    # Setup logging
    config.log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stdout,
        level=config.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    logger.add(
        config.log_dir / "daemon.log",
        rotation="10 MB",
        retention="7 days",
        level=config.log_level,
    )

    logger.info("Starting Obscura daemon")

    # Create daemon instance
    daemon = ObscuraDaemon(config)

    # Create FastAPI app
    app = create_app(daemon)

    # Configure uvicorn
    uvicorn_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(uvicorn_config)

    # Setup signal handlers
    def handle_shutdown(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        server.should_exit = True

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Run server
    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt, shutting down...")
    finally:
        logger.info("Obscura daemon stopped")


if __name__ == "__main__":
    main()
