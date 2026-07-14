"""
Message Builder and Request Context

Fluent API for building and sending messages between components.
"""

import logging
import time
from typing import Any

log = logging.getLogger(__name__)


class MessageBuilder:
    """
    Fluent interface for building and sending messages.
    """

    def __init__(self, sender):
        self.sender = sender
        self._target = None
        self._data = {}
        self._timeout = 5.0

    def to(self, target_component: str) -> "MessageBuilder":
        """Set the target component."""
        self._target = target_component
        return self

    def with_data(self, data: dict) -> "MessageBuilder":
        """Set the message data."""
        self._data = data
        return self

    def timeout(self, seconds: float) -> "MessageBuilder":
        """Set timeout for response."""
        self._timeout = seconds
        return self

    async def send_and_wait(self) -> Any:
        """Send message and wait for response."""
        if not self._target:
            raise ValueError("Target component not specified")

        return await self.sender.request(self._target, self._data, self._timeout)


class RequestContext:
    """Context manager for request/response lifecycle management."""

    def __init__(self, agent, target: str, timeout: float = 5.0):
        self.agent = agent
        self.target = target
        self.timeout = timeout
        self._request_id = None
        self._start_time = None

    async def __aenter__(self):
        """Setup for request."""
        self._start_time = time.time()
        log.debug(f"[RequestContext] Starting request context for {self.target}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup resources."""
        duration = time.time() - self._start_time if self._start_time else 0
        log.debug(f"[RequestContext] Request context completed in {duration:.3f}s")

        # Cleanup any pending request data if needed
        if hasattr(self.agent, "_received_responses") and self._request_id:
            self.agent._received_responses.pop(self._request_id, None)

    async def send(self, data: dict) -> Any:
        """Send data and return response."""
        result = await self.agent.request(self.target, data, self.timeout)
        return result
