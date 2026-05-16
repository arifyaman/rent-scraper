#!/usr/bin/env python3
"""Run the kv.ee monitor as a background service with hourly checks."""
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime

import config

# Setup logging to file
log_dir = config.LOG_DIR
log_file = config.LOG_FILE

import os
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Graceful shutdown
shutdown_event = asyncio.Event()


def signal_handler():
    logger.info("Shutdown signal received...")
    shutdown_event.set()


async def run_once():
    """Execute a single scrape cycle."""
    import monitor

    try:
        await monitor.main()
    except Exception as e:
        logger.exception(f"Error during scrape cycle: {e}")


async def main():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    logger.info("=" * 60)
    logger.info("kv.ee Rental Monitor Service STARTED")
    logger.info(f"Check interval: {config.CHECK_INTERVAL_SECONDS}s ({config.CHECK_INTERVAL_SECONDS/3600:.1f}h)")
    logger.info("=" * 60)

    while not shutdown_event.is_set():
        start = time.time()
        await run_once()

        elapsed = time.time() - start
        next_check = config.CHECK_INTERVAL_SECONDS - elapsed

        if next_check > 0 and not shutdown_event.is_set():
            logger.info(f"Next check in {next_check:.0f}s ({next_check/3600:.2f}h)...")
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=next_check)
            except asyncio.TimeoutError:
                pass

    logger.info("Service stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
