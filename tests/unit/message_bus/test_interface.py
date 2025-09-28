"""Tests for MessageBus interface and data structures."""

import pytest
import time
from unittest.mock import Mock
from woodwork.core.message_bus.interface import (
    MessageEnvelope, MessageDeliveryMode, MessagePattern
)


class TestMessageEnvelope:
    """Test suite for MessageEnvelope."""

    def test_basic_creation(self):
        """Test creating a basic message envelope."""
        envelope = MessageEnvelope(
            message_id="test_123",
            session_id="session_456",
            event_type="test.event",
            payload={"data": "test"}
        )

        assert envelope.message_id == "test_123"
        assert envelope.session_id == "session_456"
        assert envelope.event_type == "test.event"
        assert envelope.payload == {"data": "test"}
        assert envelope.sender_component is None
        assert envelope.target_component is None
        assert envelope.delivery_mode == MessageDeliveryMode.AT_LEAST_ONCE
        assert envelope.pattern == MessagePattern.POINT_TO_POINT
        assert envelope.retry_count == 0
        assert envelope.max_retries == 3
        assert envelope.ttl_seconds == 300

    def test_creation_with_all_fields(self):
        """Test creating envelope with all fields specified."""
        envelope = MessageEnvelope(
            message_id="msg_789",
            session_id="session_abc",
            event_type="agent.action",
            payload={"action": "test", "data": {"key": "value"}},
            sender_component="agent1",
            target_component="tool1",
            delivery_mode=MessageDeliveryMode.AT_MOST_ONCE,
            pattern=MessagePattern.PUBLISH_SUBSCRIBE,
            retry_count=1,
            max_retries=5,
            ttl_seconds=600
        )

        assert envelope.message_id == "msg_789"
        assert envelope.session_id == "session_abc"
        assert envelope.event_type == "agent.action"
        assert envelope.sender_component == "agent1"
        assert envelope.target_component == "tool1"
        assert envelope.delivery_mode == MessageDeliveryMode.AT_MOST_ONCE
        assert envelope.pattern == MessagePattern.PUBLISH_SUBSCRIBE
        assert envelope.retry_count == 1
        assert envelope.max_retries == 5
        assert envelope.ttl_seconds == 600

    def test_created_at_timestamp(self):
        """Test that created_at is set to current time."""
        before = time.time()
        envelope = MessageEnvelope(
            message_id="test",
            session_id="session",
            event_type="test.event",
            payload={}
        )
        after = time.time()

        assert before <= envelope.created_at <= after

    def test_delivery_modes(self):
        """Test different delivery modes."""
        # AT_MOST_ONCE
        envelope1 = MessageEnvelope(
            message_id="1", session_id="s", event_type="e", payload={},
            delivery_mode=MessageDeliveryMode.AT_MOST_ONCE
        )
        assert envelope1.delivery_mode == MessageDeliveryMode.AT_MOST_ONCE

        # AT_LEAST_ONCE (default)
        envelope2 = MessageEnvelope(
            message_id="2", session_id="s", event_type="e", payload={}
        )
        assert envelope2.delivery_mode == MessageDeliveryMode.AT_LEAST_ONCE

        # EXACTLY_ONCE
        envelope3 = MessageEnvelope(
            message_id="3", session_id="s", event_type="e", payload={},
            delivery_mode=MessageDeliveryMode.EXACTLY_ONCE
        )
        assert envelope3.delivery_mode == MessageDeliveryMode.EXACTLY_ONCE

    def test_message_patterns(self):
        """Test different message patterns."""
        # POINT_TO_POINT (default)
        envelope1 = MessageEnvelope(
            message_id="1", session_id="s", event_type="e", payload={}
        )
        assert envelope1.pattern == MessagePattern.POINT_TO_POINT

        # PUBLISH_SUBSCRIBE
        envelope2 = MessageEnvelope(
            message_id="2", session_id="s", event_type="e", payload={},
            pattern=MessagePattern.PUBLISH_SUBSCRIBE
        )
        assert envelope2.pattern == MessagePattern.PUBLISH_SUBSCRIBE

    def test_retry_logic_fields(self):
        """Test retry-related fields."""
        envelope = MessageEnvelope(
            message_id="retry_test",
            session_id="session",
            event_type="test.event",
            payload={},
            max_retries=10
        )

        assert envelope.retry_count == 0  # Starts at 0
        assert envelope.max_retries == 10

        # Simulate retry increment
        envelope.retry_count += 1
        assert envelope.retry_count == 1

    def test_ttl_configuration(self):
        """Test TTL (time-to-live) configuration."""
        # Default TTL
        envelope1 = MessageEnvelope(
            message_id="1", session_id="s", event_type="e", payload={}
        )
        assert envelope1.ttl_seconds == 300

        # Custom TTL
        envelope2 = MessageEnvelope(
            message_id="2", session_id="s", event_type="e", payload={},
            ttl_seconds=1800  # 30 minutes
        )
        assert envelope2.ttl_seconds == 1800

        # No TTL
        envelope3 = MessageEnvelope(
            message_id="3", session_id="s", event_type="e", payload={},
            ttl_seconds=None
        )
        assert envelope3.ttl_seconds is None

    def test_complex_payload(self):
        """Test envelope with complex payload."""
        complex_payload = {
            "action": "execute_tool",
            "data": {
                "tool_name": "github_api",
                "arguments": {
                    "repo": "test/repo",
                    "issue_number": 42
                },
                "metadata": {
                    "request_id": "req_123",
                    "timestamp": 1234567890
                }
            },
            "session_context": {
                "user_id": "user_456",
                "conversation_id": "conv_789"
            }
        }

        envelope = MessageEnvelope(
            message_id="complex_test",
            session_id="session",
            event_type="tool.execute",
            payload=complex_payload
        )

        assert envelope.payload == complex_payload
        assert envelope.payload["action"] == "execute_tool"
        assert envelope.payload["data"]["tool_name"] == "github_api"
        assert envelope.payload["session_context"]["user_id"] == "user_456"


class TestMessageEnums:
    """Test the enum types used in message bus."""

    def test_delivery_mode_enum(self):
        """Test MessageDeliveryMode enum values."""
        assert MessageDeliveryMode.AT_MOST_ONCE.value == "at_most_once"
        assert MessageDeliveryMode.AT_LEAST_ONCE.value == "at_least_once"
        assert MessageDeliveryMode.EXACTLY_ONCE.value == "exactly_once"

    def test_message_pattern_enum(self):
        """Test MessagePattern enum values."""
        assert MessagePattern.POINT_TO_POINT.value == "point_to_point"
        assert MessagePattern.PUBLISH_SUBSCRIBE.value == "publish_subscribe"

    def test_enum_equality(self):
        """Test enum equality comparisons."""
        mode1 = MessageDeliveryMode.AT_LEAST_ONCE
        mode2 = MessageDeliveryMode.AT_LEAST_ONCE
        mode3 = MessageDeliveryMode.AT_MOST_ONCE

        assert mode1 == mode2
        assert mode1 != mode3

        pattern1 = MessagePattern.POINT_TO_POINT
        pattern2 = MessagePattern.PUBLISH_SUBSCRIBE

        assert pattern1 != pattern2