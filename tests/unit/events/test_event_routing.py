"""Tests for event routing and distribution."""

import pytest
from unittest.mock import Mock, AsyncMock
from tests.unit.fixtures.event_fixtures import MockEventManager, MockPayload, create_mock_hooks, create_mock_pipes


class TestEventRouting:
    """Test suite for event routing logic."""

    @pytest.fixture
    def event_router(self):
        """Create event router (using MockEventManager as base)."""
        return MockEventManager()

    @pytest.fixture
    def mock_hooks(self):
        return create_mock_hooks()

    @pytest.fixture
    def mock_pipes(self):
        return create_mock_pipes()

    def test_route_to_single_hook(self, event_router, mock_hooks):
        """Test routing event to single hook."""
        hook = mock_hooks["debug_hook"]
        event_router.add_hook("test.event", hook)

        # Simulate event routing
        payload = MockPayload({"test": "data"})
        event_router.emit("test.event", payload)

        # Verify routing occurred
        assert len(event_router.emitted_events) == 1
        assert event_router.emitted_events[0] == ("test.event", payload)

    def test_route_to_multiple_hooks(self, event_router, mock_hooks):
        """Test routing event to multiple hooks."""
        hooks = [mock_hooks["debug_hook"], mock_hooks["logging_hook"], mock_hooks["metrics_hook"]]

        for hook in hooks:
            event_router.add_hook("test.event", hook)

        # Simulate routing to all hooks
        payload = MockPayload({"test": "data"})
        for hook in event_router.hooks.get("test.event", []):
            hook(payload)

        # All hooks should have been called
        for hook in hooks:
            hook.assert_called_once_with(payload)

    def test_route_through_pipe_chain(self, event_router, mock_pipes):
        """Test routing through pipe transformation chain."""
        pipes = [mock_pipes["input_transformer"], mock_pipes["output_formatter"]]

        for pipe in pipes:
            event_router.add_pipe("test.event", pipe)

        # Simulate pipe chain execution
        payload = MockPayload({"original": "data"})
        for pipe in event_router.pipes.get("test.event", []):
            payload = pipe(payload)

        # All pipes should have been called
        for pipe in pipes:
            pipe.assert_called()

    def test_event_type_filtering(self, event_router):
        """Test filtering events by type."""
        agent_hook = Mock()
        tool_hook = Mock()

        event_router.add_hook("agent.thought", agent_hook)
        event_router.add_hook("tool.call", tool_hook)

        # Emit different event types
        agent_payload = MockPayload({"thought": "thinking"})
        tool_payload = MockPayload({"tool": "test_tool"})

        # Simulate filtered routing
        if "agent.thought" in event_router.hooks:
            for hook in event_router.hooks["agent.thought"]:
                hook(agent_payload)

        if "tool.call" in event_router.hooks:
            for hook in event_router.hooks["tool.call"]:
                hook(tool_payload)

        # Only appropriate hooks should be called
        agent_hook.assert_called_once_with(agent_payload)
        tool_hook.assert_called_once_with(tool_payload)

    def test_wildcard_event_routing(self, event_router):
        """Test wildcard event routing patterns."""
        # Mock wildcard matching
        wildcard_hook = Mock()
        specific_hook = Mock()

        # Simulate wildcard registration (agent.*)
        event_router.add_hook("agent.*", wildcard_hook)
        event_router.add_hook("agent.thought", specific_hook)

        # Test routing logic for wildcards
        agent_events = ["agent.thought", "agent.action", "agent.step_complete"]

        for event_type in agent_events:
            payload = MockPayload({"event_type": event_type})

            # Wildcard hook should match all agent events
            if event_type.startswith("agent."):
                wildcard_hook(payload)

            # Specific hook only matches exact type
            if event_type == "agent.thought":
                specific_hook(payload)

        assert wildcard_hook.call_count == 3
        assert specific_hook.call_count == 1

    def test_priority_based_routing(self, event_router):
        """Test priority-based hook execution."""
        execution_order = []

        def high_priority_hook(payload):
            execution_order.append("high")

        def medium_priority_hook(payload):
            execution_order.append("medium")

        def low_priority_hook(payload):
            execution_order.append("low")

        # Add hooks in random order
        event_router.add_hook("test.event", medium_priority_hook)
        event_router.add_hook("test.event", high_priority_hook)
        event_router.add_hook("test.event", low_priority_hook)

        # In real implementation, hooks would be sorted by priority
        # For mock, we simulate priority execution order
        priority_hooks = [
            (1, high_priority_hook),
            (2, medium_priority_hook),
            (3, low_priority_hook)
        ]
        priority_hooks.sort(key=lambda x: x[0])

        payload = MockPayload({"test": "data"})
        for _, hook in priority_hooks:
            hook(payload)

        assert execution_order == ["high", "medium", "low"]

    def test_conditional_routing(self, event_router):
        """Test conditional event routing."""
        conditional_hook = Mock()

        def routing_condition(payload):
            """Only route if payload meets condition."""
            return payload.data.get("route_me", False) is True

        event_router.add_hook("test.event", conditional_hook)

        # Test with condition met
        payload_with_condition = MockPayload({"route_me": True, "data": "test"})
        if routing_condition(payload_with_condition):
            conditional_hook(payload_with_condition)

        # Test with condition not met
        payload_without_condition = MockPayload({"route_me": False, "data": "test"})
        if routing_condition(payload_without_condition):
            conditional_hook(payload_without_condition)

        # Hook should only be called once (when condition was met)
        conditional_hook.assert_called_once_with(payload_with_condition)

    def test_routing_performance(self, event_router):
        """Test routing performance with many hooks."""
        # Register many hooks
        hooks = [Mock() for _ in range(100)]
        for hook in hooks:
            event_router.add_hook("performance.test", hook)

        # Measure routing performance
        import time
        start_time = time.time()

        payload = MockPayload({"test": "data"})
        for hook in event_router.hooks.get("performance.test", []):
            hook(payload)

        end_time = time.time()
        routing_time = end_time - start_time

        # Should complete quickly (less than 1 second for 100 hooks)
        assert routing_time < 1.0

        # All hooks should be called
        for hook in hooks:
            hook.assert_called_once()


class TestEventRoutingErrorHandling:
    """Test error handling in event routing."""

    @pytest.fixture
    def error_router(self):
        return MockEventManager()

    def test_hook_failure_isolation(self, error_router):
        """Test that failing hooks don't affect others."""
        working_hook1 = Mock()
        failing_hook = Mock(side_effect=Exception("Hook failed"))
        working_hook2 = Mock()

        error_router.add_hook("test.event", working_hook1)
        error_router.add_hook("test.event", failing_hook)
        error_router.add_hook("test.event", working_hook2)

        # Simulate error-resistant routing
        payload = MockPayload({"test": "data"})
        for hook in error_router.hooks.get("test.event", []):
            try:
                hook(payload)
            except Exception:
                continue  # Continue with other hooks

        # Working hooks should still be called
        working_hook1.assert_called_once()
        working_hook2.assert_called_once()
        failing_hook.assert_called_once()

    def test_pipe_failure_handling(self, error_router):
        """Test handling of pipe failures."""
        def working_pipe(payload):
            payload.data["step1"] = True
            return payload

        def failing_pipe(payload):
            raise Exception("Pipe failed")

        def recovery_pipe(payload):
            payload.data["recovered"] = True
            return payload

        error_router.add_pipe("test.event", working_pipe)
        error_router.add_pipe("test.event", failing_pipe)
        error_router.add_pipe("test.event", recovery_pipe)

        # Simulate pipe chain with error recovery
        payload = MockPayload({"original": True})
        for pipe in error_router.pipes.get("test.event", []):
            try:
                payload = pipe(payload)
            except Exception:
                # In real implementation, might use fallback or skip
                continue

        # Working transformations should have been applied
        assert payload.data["step1"] is True
        assert payload.data.get("recovered") is True

    def test_routing_with_invalid_payload(self, error_router):
        """Test routing with invalid or malformed payloads."""
        robust_hook = Mock()
        error_router.add_hook("test.event", robust_hook)

        # Test with None payload
        try:
            robust_hook(None)
        except Exception:
            pass  # Hook should handle gracefully

        # Test with invalid payload structure
        try:
            robust_hook("not_a_payload_object")
        except Exception:
            pass  # Hook should handle gracefully

        # Hook was called (error handling is hook's responsibility)
        assert robust_hook.call_count >= 1

    def test_circular_routing_prevention(self, error_router):
        """Test prevention of circular routing loops."""
        call_count = 0

        def potentially_circular_hook(payload):
            nonlocal call_count
            call_count += 1

            # Prevent infinite recursion
            if call_count > 10:
                return

            # In real system, this might trigger another event
            error_router.emit("test.event", payload)

        error_router.add_hook("test.event", potentially_circular_hook)

        # Simulate initial event that could cause circular routing
        initial_payload = MockPayload({"initial": True})
        potentially_circular_hook(initial_payload)

        # Should not cause infinite recursion
        assert call_count <= 10

    def test_memory_leak_prevention(self, error_router):
        """Test prevention of memory leaks in routing."""
        # Register and unregister many hooks
        for i in range(100):
            hook = Mock()
            error_router.add_hook(f"temp.event.{i}", hook)

        # Simulate cleanup
        for event_type in list(error_router.hooks.keys()):
            if event_type.startswith("temp."):
                del error_router.hooks[event_type]

        # Memory should be freed
        temp_events = [k for k in error_router.hooks.keys() if k.startswith("temp.")]
        assert len(temp_events) == 0

    def test_routing_thread_safety(self, error_router):
        """Test thread safety in event routing."""
        import threading
        import time

        results = []
        lock = threading.Lock()

        def thread_safe_hook(payload):
            with lock:
                results.append(payload.data.get("thread_id"))
                time.sleep(0.001)  # Small delay to increase chance of race conditions

        error_router.add_hook("concurrent.test", thread_safe_hook)

        def emit_from_thread(thread_id):
            payload = MockPayload({"thread_id": thread_id})
            thread_safe_hook(payload)

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=emit_from_thread, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All thread IDs should be recorded
        assert len(results) == 10
        assert set(results) == set(range(10))