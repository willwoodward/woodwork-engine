"""Default configuration values for Woodwork.

All values can be overridden via environment variables.
"""

import os

NEO4J_URI = os.getenv("WOODWORK_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("WOODWORK_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("WOODWORK_NEO4J_PASSWORD", "testpassword")
NEO4J_AUTH = f"{NEO4J_USER}/{NEO4J_PASSWORD}"
