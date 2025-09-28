"""Test message fixtures and utilities."""

from dataclasses import dataclass
from typing import Dict, Any
from woodwork.core.message_bus.interface import MessageEnvelope


@dataclass
class MockMessageEnvelope:
    """Mock message envelope with default values."""
    message_id: str = "test_message_123"
    session_id: str = "test_session"
    event_type: str = "test_event"
    payload: Dict[str, Any] = None
    target_component: str = "test_target"
    sender_component: str = "test_sender"
    timestamp: float = 1000.0
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.payload is None:
            self.payload = {}

    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.retry_count < self.max_retries


def create_component_message(
    source: str = "test_source",
    target: str = "test_target",
    data: Dict[str, Any] = None,
    response_required: bool = False,
    request_id: str = None
) -> MockMessageEnvelope:
    """Create a test component message."""
    payload = {
        "data": data or {},
        "source_component": source,
        "routed_at": 1000.0
    }

    if response_required:
        payload.update({
            "_response_required": True,
            "_request_id": request_id or f"{source}_{target}_1000000",
            "_response_target": source
        })

    return MockMessageEnvelope(
        event_type="component_message",
        payload=payload,
        target_component=target,
        sender_component=source
    )


def create_response_message(
    source: str = "test_tool",
    target: str = "test_agent",
    result: str = "test_result",
    request_id: str = "test_request_123"
) -> MockMessageEnvelope:
    """Create a test response message."""
    return MockMessageEnvelope(
        event_type="component_message",
        payload={
            "data": {
                "result": result,
                "request_id": request_id,
                "source_component": source,
                "response_type": "component_response"
            },
            "source_component": source,
            "routed_at": 1000.0
        },
        target_component=target,
        sender_component=source
    )


def create_hook_message(
    event_type: str = "agent.thought",
    data: Dict[str, Any] = None,
    source: str = "test_agent"
) -> MockMessageEnvelope:
    """Create a test hook message."""
    return MockMessageEnvelope(
        event_type=event_type,
        payload={
            "data": data or {"thought": "test thought"},
            "source_component": source,
            "broadcast_at": 1000.0
        },
        sender_component=source
    )