#!/usr/bin/env python3
"""
Test script for the FastAPI GUI server.

This script can be used to test the FastAPI GUI server independently.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from woodwork.gui.fastapi_gui_server import start_gui_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Test the FastAPI GUI server."""
    logger.info("Testing FastAPI GUI Server...")

    try:
        await start_gui_server()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("FastAPI GUI Server test completed")
    except Exception as e:
        logger.error(f"Failed to start FastAPI GUI Server: {e}")
        sys.exit(1)