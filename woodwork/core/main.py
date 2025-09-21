"""
Main entry point for Woodwork engine with unified async runtime

This replaces the distributed startup system with a unified async runtime
that eliminates threading issues and provides real-time event delivery.
"""

import asyncio
import logging
import sys
from typing import Dict, Any

from woodwork.core.async_runtime import AsyncRuntime
from woodwork.parser.config_parser import parse_config_file, parse_config_dict

log = logging.getLogger(__name__)


async def start_woodwork(config_path: str = None, config_dict: Dict[str, Any] = None) -> None:
    """
    Start Woodwork engine with unified async runtime.

    Args:
        config_path: Path to .ww configuration file
        config_dict: Configuration dictionary (alternative to file)
    """
    try:
        # Parse configuration
        if config_path:
            log.info("[Woodwork] Starting with config file: %s", config_path)
            config = parse_config_file(config_path)
        elif config_dict:
            log.info("[Woodwork] Starting with config dictionary")
            config = parse_config_dict(config_dict)
        else:
            raise ValueError("Either config_path or config_dict must be provided")

        # Create and start async runtime
        runtime = AsyncRuntime()
        await runtime.start(config)

    except KeyboardInterrupt:
        log.info("[Woodwork] Shutdown requested")
    except Exception as e:
        log.error("[Woodwork] Error starting Woodwork: %s", e)
        raise
    finally:
        log.info("[Woodwork] Shutting down")


def main():
    """Command line entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Woodwork Engine with Unified Runtime")
    parser.add_argument("config", nargs="?", help="Path to .ww configuration file")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Default config if none provided
    config_path = args.config or "main.ww"

    # Check if config file exists
    import os
    if not os.path.exists(config_path):
        log.error("Configuration file not found: %s", config_path)
        sys.exit(1)

    # Start async runtime
    try:
        asyncio.run(start_woodwork(config_path=config_path))
    except KeyboardInterrupt:
        log.info("Interrupted by user")
    except Exception as e:
        log.error("Failed to start: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()