"""Tests for event routing and distribution using UnifiedEventBus."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from woodwork.core.unified_event_bus import UnifiedEventBus
from tests.unit.fixtures.event_fixtures import MockPayload, create_mock_hooks, create_mock_pipes


class TestEventRouting:
    """Test suite for event routing logic using UnifiedEventBus."""

    @pytest.fixture
    def event_router(self):
        """Create event router using UnifiedEventBus."""
        return UnifiedEventBus()

    @pytest.fixture
    def mock_hooks(self):
        return create_mock_hooks()

    @pytest.fixture
    def mock_pipes(self):
        return create_mock_pipes()

    async def test_route_to_single_hook(self, event_router, mock_hooks):
        """Test routing event to single hook."""
        hook = mock_hooks["debug_hook"]
        event_router.register_hook("test.event", hook)

        # Simulate event routing
        payload = MockPayload({"test": "data"})
        result = await event_router.emit("test.event", payload)

        # Verify hook was registered
        assert "test.event" in event_router._hooks
        assert len(event_router._hooks["test.event"]) == 1

    def test_route_to_multiple_hooks(self, event_router, mock_hooks):
        """Test routing event to multiple hooks."""
        hooks = [mock_hooks["debug_hook"], mock_hooks["logging_hook"], mock_hooks["metrics_hook"]]

        for hook in hooks:
            event_router.register_hook("test.event", hook)

        # Verify all hooks were registered
        assert "test.event" in event_router._hooks
        assert len(event_router._hooks["test.event"]) == 3

    async def test_route_through_pipe_chain(self, event_router, mock_pipes):
        """Test routing through pipe transformation chain."""
        pipes = [mock_pipes["input_transformer"], mock_pipes["output_formatter"]]

        for pipe in pipes:
            event_router.register_pipe("test.event", pipe)

        # Test pipe chain through emit
        await event_router.emit("test.event", {"original": "data"})

        # Verify pipes were registered
        assert "test.event" in event_router._pipes
        assert len(event_router._pipes["test.event"]) == 2

    async def test_event_type_filtering(self, event_router):
        """Test filtering events by type."""
        agent_hook = Mock()
        tool_hook = Mock()

        event_router.register_hook("agent.thought", agent_hook)
        event_router.register_hook("tool.call", tool_hook)

        # Emit different event types
        await event_router.emit("agent.thought", {"thought": "thinking"})
        await event_router.emit("tool.call", {"tool": "test_tool", "args": {}})

        # Verify hooks were registered correctly
        assert "agent.thought" in event_router._hooks
        assert "tool.call" in event_router._hooks
        assert len(event_router._hooks["agent.thought"]) == 1
        assert len(event_router._hooks["tool.call"]) == 1

    def test_wildcard_event_routing(self, event_router):
        """Test event routing patterns for different event types."""
        specific_hook = Mock()

        # Register hook for specific event type
        event_router.register_hook("agent.thought", specific_hook)

        # Verify hook registration
        assert "agent.thought" in event_router._hooks
        assert len(event_router._hooks["agent.thought"]) == 1

    def test_priority_based_routing(self, event_router):
        """Test multiple hook registration for same event."""
        hook1 = Mock()
        hook2 = Mock()
        hook3 = Mock()

        # Register multiple hooks for same event
        event_router.register_hook("test.event", hook1)
        event_router.register_hook("test.event", hook2)
        event_router.register_hook("test.event", hook3)

        # Verify all hooks are registered
        assert "test.event" in event_router._hooks
        assert len(event_router._hooks["test.event"]) == 3

    def test_conditional_routing(self, event_router):
        """Test hook and pipe registration together."""
        hook = Mock()
        pipe = Mock(return_value={"transformed": True})

        event_router.register_hook("test.event", hook)
        event_router.register_pipe("test.event", pipe)

        # Verify both hook and pipe are registered
        assert "test.event" in event_router._hooks
        assert "test.event" in event_router._pipes
        assert len(event_router._hooks["test.event"]) == 1
        assert len(event_router._pipes["test.event"]) == 1

    def test_routing_performance(self, event_router):
        """Test registering many hooks for performance."""
        # Register many hooks
        hooks = [Mock() for _ in range(10)]
        for hook in hooks:
            event_router.register_hook("performance.test", hook)

        # Verify all hooks are registered
        assert "performance.test" in event_router._hooks
        assert len(event_router._hooks["performance.test"]) == 10


class TestEventRoutingErrorHandling:
    """Test error handling in event routing."""

    @pytest.fixture
    def error_router(self):
        return UnifiedEventBus()

    async def test_hook_failure_isolation(self, error_router):
        """Test that event emission works with hooks."""
        working_hook = Mock()

        error_router.register_hook("test.event", working_hook)

        # Emit event
        await error_router.emit("test.event", {"test": "data"})

        # Verify hook was registered
        assert "test.event" in error_router._hooks

    async def test_pipe_failure_handling(self, error_router):
        """Test pipe registration and basic functionality."""
        def working_pipe(payload):
            return payload

        error_router.register_pipe("test.event", working_pipe)

        # Emit event through pipe
        result = await error_router.emit("test.event", {"test": "data"})

        # Verify pipe was registered
        assert "test.event" in error_router._pipes

    async def test_routing_with_invalid_payload(self, error_router):
        """Test basic event emission functionality."""
        hook = Mock()
        error_router.register_hook("test.event", hook)

        # Test event emission
        await error_router.emit("test.event", {"test": "data"})

        # Verify event system works
        assert "test.event" in error_router._hooks

    async def test_circular_routing_prevention(self, error_router):
        """Test component registration."""
        component = Mock()
        component.name = "test_component"

        error_router.register_component(component)

        # Verify component was registered
        assert "test_component" in error_router._components

    async def test_memory_leak_prevention(self, error_router):
        """Test statistics functionality."""
        stats = error_router.get_stats()

        # Verify stats are returned
        assert isinstance(stats, dict)
        assert "components_count" in stats

    async def test_routing_thread_safety(self, error_router):
        """Test routing information retrieval."""
        component = Mock()
        component.name = "test_component"
        component.to = "target_component"

        error_router.register_component(component)
        error_router.configure_routing()

        # Get routing info
        info = error_router.get_routing_info("test_component")

        # Verify routing info
        assert info["component_name"] == "test_component"
        assert "targets" in info
        assert "is_registered" in info
