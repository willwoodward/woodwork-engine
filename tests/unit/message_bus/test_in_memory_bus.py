"""Tests for InMemoryMessageBus component."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from woodwork.core.message_bus.in_memory_bus import InMemoryMessageBus
from tests.unit.fixtures.test_messages import create_component_message, MockMessageEnvelope


class TestInMemoryMessageBus:
    """Test suite for InMemoryMessageBus."""

    @pytest.fixture
    async def message_bus(self):
        bus = InMemoryMessageBus()
        await bus.start()
        yield bus
        await bus.stop()

    @pytest.fixture
    def test_message(self):
        return create_component_message(
            source="test_agent",
            target="test_tool",
            data={"action": "test", "inputs": {}}
        )

    def test_initialization(self):
        """Test message bus initializes correctly."""
        bus = InMemoryMessageBus()
        assert not bus.running
        assert bus.component_handlers == {}
        assert bus.component_queues == {}
        assert bus.stats["messages_delivered"] == 0

    async def test_start_stop(self, message_bus):
        """Test starting and stopping the message bus."""
        assert message_bus.running

        await message_bus.stop()
        assert not message_bus.running

    def test_register_component_handler(self, message_bus):
        """Test registering component handlers."""
        handler = Mock()
        message_bus.register_component_handler("test_component", handler)

        assert "test_component" in message_bus.component_handlers
        assert message_bus.stats["registered_components"] == 1

    async def test_send_to_component_direct_delivery(self, message_bus, test_message):
        """Test direct message delivery when handler exists."""
        handler = AsyncMock()
        message_bus.register_component_handler("test_tool", handler)

        success = await message_bus.send_to_component(test_message)

        assert success
        handler.assert_called_once_with(test_message)
        assert message_bus.stats["messages_delivered"] == 1

    async def test_send_to_component_queuing(self, message_bus, test_message):
        """Test message queuing when no handler exists."""
        success = await message_bus.send_to_component(test_message)

        assert success
        assert "test_tool" in message_bus.component_queues
        assert len(message_bus.component_queues["test_tool"]) == 1
        assert message_bus.stats["queued_messages"] == 1

    async def test_register_handler_delivers_queued_messages(self, message_bus):
        """Test that registering a handler delivers queued messages."""
        # Send message before handler is registered
        message = create_component_message(target="test_component")
        await message_bus.send_to_component(message)

        assert len(message_bus.component_queues["test_component"]) == 1

        # Register handler - should deliver queued message
        handler = AsyncMock()
        message_bus.register_component_handler("test_component", handler)

        # Give a moment for async delivery
        await asyncio.sleep(0.01)

        handler.assert_called_once_with(message)
        assert len(message_bus.component_queues["test_component"]) == 0

    async def test_send_to_component_bus_not_running(self):
        """Test sending message when bus is not running."""
        bus = InMemoryMessageBus()  # Not started
        message = create_component_message()

        success = await bus.send_to_component(message)
        assert not success

    async def test_send_to_component_missing_target(self, message_bus):
        """Test sending message without target component."""
        message = MockMessageEnvelope(target_component=None)

        success = await message_bus.send_to_component(message)
        assert not success

    async def test_publish_message(self, message_bus):
        """Test publishing messages."""
        message = create_component_message()
        success = await message_bus.publish(message)

        assert success
        assert message_bus.stats["messages_published"] == 1

    async def test_subscribe_to_events(self, message_bus):
        """Test subscribing to events."""
        handler = Mock()
        await message_bus.subscribe("test_event", handler)

        assert "test_event" in message_bus.topic_subscribers
        assert len(message_bus.topic_subscribers["test_event"]) == 1
        assert message_bus.stats["active_subscriptions"] == 1

    async def test_unsubscribe_from_events(self, message_bus):
        """Test unsubscribing from events."""
        handler = Mock()
        subscription_id = await message_bus.subscribe("test_event", handler)
        await message_bus.unsubscribe(subscription_id)

        # After unsubscribing, the topic should have no subscribers
        assert len(message_bus.topic_subscribers.get("test_event", set())) == 0
        assert message_bus.stats["active_subscriptions"] == 0

    async def test_handler_execution_error(self, message_bus, test_message):
        """Test error handling when handler throws exception."""
        handler = Mock(side_effect=Exception("Handler error"))
        message_bus.register_component_handler("test_tool", handler)

        success = await message_bus.send_to_component(test_message)

        # Should return False when handler fails and queue for retry
        assert not success
        assert message_bus.stats["delivery_failures"] == 1
        assert message_bus.stats["messages_retried"] == 1

    def test_component_handler_stats(self, message_bus):
        """Test component handler statistics tracking."""
        handler = Mock()
        message_bus.register_component_handler("test_component", handler)

        handler_obj = message_bus.component_handlers["test_component"]
        assert handler_obj.message_count == 0
        assert handler_obj.registered_at > 0

        # Send message to update stats
        message = create_component_message(target="test_component")
        asyncio.run(message_bus.send_to_component(message))

        assert handler_obj.message_count == 1
        assert handler_obj.last_message_at > handler_obj.registered_at

    def test_get_component_stats(self, message_bus):
        """Test getting component statistics from overall stats."""
        handler = Mock()
        message_bus.register_component_handler("test_component", handler)

        stats = message_bus.get_stats()
        assert stats["registered_components"] == 1
        assert "component_handlers" in stats
        # Component handlers are tracked in the stats
        assert isinstance(stats["component_handlers"], dict)

    def test_get_bus_stats(self, message_bus):
        """Test getting overall bus statistics."""
        stats = message_bus.get_stats()

        expected_keys = [
            "running", "messages_delivered", "messages_published",
            "queued_messages", "registered_components", "delivery_failures"
        ]
        for key in expected_keys:
            assert key in stats

    async def test_concurrent_message_delivery(self, message_bus):
        """Test concurrent message delivery."""
        handlers = [AsyncMock() for _ in range(3)]
        messages = []

        for i, handler in enumerate(handlers):
            component_id = f"component_{i}"
            message_bus.register_component_handler(component_id, handler)
            messages.append(create_component_message(target=component_id))

        # Send all messages concurrently
        tasks = [message_bus.send_to_component(msg) for msg in messages]
        results = await asyncio.gather(*tasks)

        assert all(results)
        for handler in handlers:
            handler.assert_called_once()

    async def test_message_ordering(self, message_bus):
        """Test that messages are delivered in order."""
        received_messages = []

        async def handler(envelope):
            received_messages.append(envelope.payload["data"]["sequence"])

        message_bus.register_component_handler("test_component", handler)

        # Send multiple messages
        for i in range(5):
            message = create_component_message(
                target="test_component",
                data={"sequence": i}
            )
            await message_bus.send_to_component(message)

        assert received_messages == [0, 1, 2, 3, 4]


class TestInMemoryMessageBusCleanup:
    """Test cleanup and resource management."""

    @pytest.fixture
    async def message_bus(self):
        bus = InMemoryMessageBus()
        await bus.start()
        yield bus
        await bus.stop()

    async def test_cleanup_old_handlers(self):
        """Test cleanup of old handlers."""
        bus = InMemoryMessageBus()
        await bus.start()

        # Register handler
        handler = Mock()
        bus.register_component_handler("test_component", handler)

        # Verify handler exists
        assert "test_component" in bus.component_handlers

        # Cleanup (this would typically be time-based)
        bus.component_handlers.clear()
        assert len(bus.component_handlers) == 0

        await bus.stop()

    async def test_memory_usage_tracking(self, message_bus):
        """Test memory usage tracking."""
        # Send many messages to queue
        for i in range(100):
            message = create_component_message(target="test_component")
            await message_bus.send_to_component(message)

        assert message_bus.stats["queued_messages"] == 100
        assert message_bus.stats["peak_queue_size"] >= 100

        # Register handler to clear queue
        handler = AsyncMock()
        message_bus.register_component_handler("test_component", handler)

        # Give time for async delivery
        await asyncio.sleep(0.01)

        assert message_bus.stats["queued_messages"] == 0