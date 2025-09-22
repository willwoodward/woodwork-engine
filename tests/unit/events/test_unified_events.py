"""
Comprehensive tests for unified event system functionality.

Tests event emission, hooks, pipes, component routing, and real-time delivery.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from woodwork.core.unified_event_bus import UnifiedEventBus
from woodwork.types import AgentThoughtPayload, ToolCallPayload, InputReceivedPayload


class TestUnifiedEvents:
    """Test suite for unified event system."""

    @pytest.fixture
    def event_bus(self):
        """Create fresh event bus for each test."""
        return UnifiedEventBus()

    @pytest.fixture
    def mock_component(self):
        """Create mock component for testing."""
        component = Mock()
        component.name = "test_component"
        component.input = AsyncMock(return_value="test_result")
        return component

    async def test_event_emission_creates_typed_payload(self, event_bus):
        """Test that emitting events creates proper typed payloads."""
        # Test agent.thought event
        result = await event_bus.emit("agent.thought", {"thought": "I'm thinking"})

        assert isinstance(result, AgentThoughtPayload)
        assert result.thought == "I'm thinking"
        assert result.timestamp is not None

    async def test_hook_registration_and_execution(self, event_bus):
        """Test hook registration and execution."""
        hook_calls = []

        def test_hook(payload):
            hook_calls.append(payload)

        # Register hook
        event_bus.register_hook("agent.thought", test_hook)

        # Emit event
        await event_bus.emit("agent.thought", {"thought": "test thought"})

        # Verify hook was called
        assert len(hook_calls) == 1
        assert isinstance(hook_calls[0], AgentThoughtPayload)
        assert hook_calls[0].thought == "test thought"

    async def test_pipe_registration_and_transformation(self, event_bus):
        """Test pipe registration and payload transformation."""
        def transform_thought(payload):
            payload.thought = f"Enhanced: {payload.thought}"
            return payload

        # Register pipe
        event_bus.register_pipe("agent.thought", transform_thought)

        # Emit event
        result = await event_bus.emit("agent.thought", {"thought": "original"})

        # Verify transformation
        assert result.thought == "Enhanced: original"

    async def test_async_hooks_and_pipes(self, event_bus):
        """Test async hooks and pipes work correctly."""
        async_hook_calls = []

        async def async_hook(payload):
            await asyncio.sleep(0.01)  # Simulate async work
            async_hook_calls.append(payload)

        async def async_pipe(payload):
            await asyncio.sleep(0.01)  # Simulate async work
            payload.thought = f"Async: {payload.thought}"
            return payload

        # Register async hook and pipe
        event_bus.register_hook("agent.thought", async_hook)
        event_bus.register_pipe("agent.thought", async_pipe)

        # Emit event
        result = await event_bus.emit("agent.thought", {"thought": "test"})

        # Verify both worked
        assert result.thought == "Async: test"
        assert len(async_hook_calls) == 1

    async def test_component_registration_and_routing(self, event_bus, mock_component):
        """Test component registration and event routing."""
        # Create routing component
        routing_component = Mock()
        routing_component.name = "router"
        routing_component.to = "test_component"  # Routes to test_component

        # Register components
        event_bus.register_component(mock_component)
        event_bus.register_component(routing_component)

        # Configure routing
        event_bus.configure_routing()

        # Verify routing table
        assert "router" in event_bus._routing_table
        assert "test_component" in event_bus._routing_table["router"]

    async def test_component_message_delivery(self, event_bus, mock_component):
        """Test direct component message delivery."""
        # Register component
        event_bus.register_component(mock_component)

        # Test send_to_component_with_response
        success, request_id = await event_bus.send_to_component_with_response(
            name="test_component",
            source_component_name="test_source",
            data={"action": "test", "inputs": {}}
        )

        # Verify delivery
        assert success
        assert request_id is not None
        mock_component.input.assert_called_once()

    async def test_multiple_event_types(self, event_bus):
        """Test emission of multiple event types."""
        events_captured = []

        def capture_event(payload):
            events_captured.append(payload.__class__.__name__)

        # Register hooks for different event types
        event_types = ["agent.thought", "tool.call", "tool.observation", "input.received"]
        for event_type in event_types:
            event_bus.register_hook(event_type, capture_event)

        # Emit different event types
        await event_bus.emit("agent.thought", {"thought": "thinking"})
        await event_bus.emit("tool.call", {"tool": "test_tool", "args": {}})
        await event_bus.emit("tool.observation", {"tool": "test_tool", "observation": "result"})
        await event_bus.emit("input.received", {"input": "test", "inputs": {}, "session_id": "test"})

        # Verify all events were captured
        expected_types = ["AgentThoughtPayload", "ToolCallPayload", "ToolObservationPayload", "InputReceivedPayload"]
        assert len(events_captured) == 4
        for expected_type in expected_types:
            assert expected_type in events_captured

    async def test_event_statistics(self, event_bus):
        """Test event bus statistics tracking."""
        # Emit several events
        await event_bus.emit("agent.thought", {"thought": "test1"})
        await event_bus.emit("agent.thought", {"thought": "test2"})
        await event_bus.emit("tool.call", {"tool": "test", "args": {}})

        # Check statistics
        stats = event_bus.get_stats()
        assert "components_count" in stats
        assert stats["components_count"] == 0  # No components registered in this test

    async def test_concurrent_event_processing(self, event_bus):
        """Test that concurrent events are processed correctly."""
        results = []

        async def slow_hook(payload):
            await asyncio.sleep(0.05)  # Simulate slow processing
            results.append(payload.thought)

        event_bus.register_hook("agent.thought", slow_hook)

        # Emit multiple events concurrently
        tasks = []
        for i in range(5):
            task = event_bus.emit("agent.thought", {"thought": f"thought_{i}"})
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

        # Verify all were processed
        assert len(results) == 5
        for i in range(5):
            assert f"thought_{i}" in results

    async def test_error_handling_in_hooks(self, event_bus):
        """Test that errors in hooks don't break event processing."""
        successful_calls = []

        def failing_hook(payload):
            raise Exception("Hook error!")

        def working_hook(payload):
            successful_calls.append(payload)

        # Register both hooks
        event_bus.register_hook("agent.thought", failing_hook)
        event_bus.register_hook("agent.thought", working_hook)

        # Emit event (should not raise exception)
        result = await event_bus.emit("agent.thought", {"thought": "test"})

        # Verify working hook still worked
        assert len(successful_calls) == 1
        assert result.thought == "test"

    async def test_pipe_error_handling(self, event_bus):
        """Test that errors in pipes are handled gracefully."""
        def failing_pipe(payload):
            raise Exception("Pipe error!")

        event_bus.register_pipe("agent.thought", failing_pipe)

        # Emit event (should not raise exception)
        result = await event_bus.emit("agent.thought", {"thought": "test"})

        # Should return original payload when pipe fails
        assert result.thought == "test"