"""
Message Bus Error Classes and Data Types

Error classes for message bus communication and the StreamingChunk dataclass.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class StreamingChunk:
    """Represents a chunk in a streaming response."""

    data: Any
    is_final: bool = False
    chunk_index: int = 0
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ComponentNotFoundError(Exception):
    """Raised when target component is not found."""

    pass


class ResponseTimeoutError(Exception):
    """Raised when response is not received within timeout."""

    pass


class ComponentError(Exception):
    """Raised when target component throws an exception."""

    pass
