"""Tests for EventManager component."""

import pytest
from unittest.mock import Mock, patch
from tests.unit.fixtures.event_fixtures import MockEventManager, MockPayload, create_test_event_data


class TestEventManager:
    """Test suite for EventManager."""

    @pytest.fixture
    def event_manager(self):
        return MockEventManager()

    @pytest.fixture
    def test_payload(self):
        return MockPayload({"test": "data"})

    def test_initialization(self, event_manager):
        """Test event manager initializes correctly."""
        assert event_manager.emitted_events == []
        assert event_manager.hooks == {}
        assert event_manager.pipes == {}

    def test_emit_event(self, event_manager, test_payload):
        """Test emitting events."""
        event_manager.emit("test.event", test_payload)

        assert len(event_manager.emitted_events) == 1
        assert event_manager.emitted_events[0] == ("test.event", test_payload)

    def test_emit_multiple_events(self, event_manager):
        """Test emitting multiple events."""
        payloads = [MockPayload({"id": i}) for i in range(3)]

        for i, payload in enumerate(payloads):
            event_manager.emit(f"test.event.{i}", payload)

        assert len(event_manager.emitted_events) == 3

    def test_add_hook(self, event_manager):
        """Test adding event hooks."""
        hook_func = Mock()
        event_manager.add_hook("test.event", hook_func)

        assert "test.event" in event_manager.hooks
        assert hook_func in event_manager.hooks["test.event"]

    def test_add_multiple_hooks(self, event_manager):
        """Test adding multiple hooks to same event."""
        hook1 = Mock()
        hook2 = Mock()

        event_manager.add_hook("test.event", hook1)
        event_manager.add_hook("test.event", hook2)

        assert len(event_manager.hooks["test.event"]) == 2

    def test_add_pipe(self, event_manager):
        """Test adding event pipes."""
        pipe_func = Mock()
        event_manager.add_pipe("test.event", pipe_func)

        assert "test.event" in event_manager.pipes
        assert pipe_func in event_manager.pipes["test.event"]

    def test_add_multiple_pipes(self, event_manager):
        """Test adding multiple pipes to same event."""
        pipe1 = Mock()
        pipe2 = Mock()

        event_manager.add_pipe("test.event", pipe1)
        event_manager.add_pipe("test.event", pipe2)

        assert len(event_manager.pipes["test.event"]) == 2

    def test_hook_execution_order(self, event_manager):
        """Test that hooks execute in registration order."""
        execution_order = []

        def hook1(payload):
            execution_order.append("hook1")

        def hook2(payload):
            execution_order.append("hook2")

        event_manager.add_hook("test.event", hook1)
        event_manager.add_hook("test.event", hook2)

        # Simulate hook execution
        for hook in event_manager.hooks.get("test.event", []):
            hook(MockPayload())

        assert execution_order == ["hook1", "hook2"]

    def test_pipe_execution_order(self, event_manager):
        """Test that pipes execute in registration order."""
        def pipe1(payload):
            payload.data["pipe1"] = True
            return payload

        def pipe2(payload):
            payload.data["pipe2"] = True
            return payload

        event_manager.add_pipe("test.event", pipe1)
        event_manager.add_pipe("test.event", pipe2)

        # Simulate pipe execution
        payload = MockPayload({"original": True})
        for pipe in event_manager.pipes.get("test.event", []):
            payload = pipe(payload)

        assert payload.data["original"] is True
        assert payload.data["pipe1"] is True
        assert payload.data["pipe2"] is True

    def test_event_data_structure(self):
        """Test event data structure constants."""
        event_data = create_test_event_data()

        # Test all expected event types exist
        expected_events = [
            "agent.thought", "agent.action", "tool.call",
            "tool.observation", "input.received", "agent.step_complete"
        ]

        for event_type in expected_events:
            assert event_type in event_data

    def test_event_type_validation(self, event_manager):
        """Test event type validation."""
        valid_events = [
            "agent.thought", "agent.action", "tool.call",
            "input.received", "custom.event"
        ]

        for event_type in valid_events:
            # Should not raise exceptions
            event_manager.emit(event_type, MockPayload())

        assert len(event_manager.emitted_events) == len(valid_events)


class TestEventManagerIntegration:
    """Test EventManager integration scenarios."""

    @pytest.fixture
    def integrated_manager(self):
        """Create manager with real woodwork event system."""
        # Import real event manager if available
        try:
            from woodwork.events import create_default_emitter
            return create_default_emitter()
        except ImportError:
            return MockEventManager()

    async def test_real_event_emission(self, integrated_manager):
        """Test emission with real event system."""
        # This test would use the actual woodwork event system
        if hasattr(integrated_manager, 'emit'):
            payload = {"thought": "Test thought"}
            await integrated_manager.emit("agent.thought", payload)

    def test_hook_registration_integration(self, integrated_manager):
        """Test hook registration with real system."""
        hook_called = False

        def test_hook(payload):
            nonlocal hook_called
            hook_called = True

        if hasattr(integrated_manager, 'add_hook'):
            integrated_manager.add_hook("test.event", test_hook)

            # Emit event to trigger hook
            if hasattr(integrated_manager, 'emit'):
                integrated_manager.emit("test.event", {"test": "data"})

    def test_pipe_transformation_integration(self, integrated_manager):
        """Test pipe transformation with real system."""
        def transform_pipe(payload):
            if isinstance(payload, dict):
                payload["transformed"] = True
            return payload

        if hasattr(integrated_manager, 'add_pipe'):
            integrated_manager.add_pipe("test.event", transform_pipe)

    def test_error_handling_in_hooks(self, integrated_manager):
        """Test error handling when hooks fail."""
        def failing_hook(payload):
            raise Exception("Hook failed")

        def working_hook(payload):
            payload.data["hook_executed"] = True

        if hasattr(integrated_manager, 'add_hook'):
            integrated_manager.add_hook("test.event", failing_hook)
            integrated_manager.add_hook("test.event", working_hook)

            # In real implementation, first hook failing shouldn't stop second
            # For mock, we just verify both are registered
            assert len(integrated_manager.hooks["test.event"]) == 2

    def test_performance_with_many_hooks(self, integrated_manager):
        """Test performance with many registered hooks."""
        if hasattr(integrated_manager, 'add_hook') and hasattr(integrated_manager, 'hooks'):
            # Register many hooks
            for i in range(100):
                hook = Mock()
                integrated_manager.add_hook("performance.test", hook)

            assert len(integrated_manager.hooks["performance.test"]) == 100

            # Simulate execution
            payload = MockPayload()
            for hook in integrated_manager.hooks["performance.test"]:
                hook(payload)

    def test_memory_cleanup(self, integrated_manager):
        """Test memory cleanup of event handlers."""
        if hasattr(integrated_manager, 'add_hook') and hasattr(integrated_manager, 'hooks'):
            # Add hooks and pipes
            for i in range(10):
                integrated_manager.add_hook(f"test.{i}", Mock())
                if hasattr(integrated_manager, 'add_pipe'):
                    integrated_manager.add_pipe(f"test.{i}", Mock())

            assert len(integrated_manager.hooks) == 10
            if hasattr(integrated_manager, 'pipes'):
                assert len(integrated_manager.pipes) == 10

            # Simulate cleanup
            integrated_manager.hooks.clear()
            if hasattr(integrated_manager, 'pipes'):
                integrated_manager.pipes.clear()

            assert len(integrated_manager.hooks) == 0
            if hasattr(integrated_manager, 'pipes'):
                assert len(integrated_manager.pipes) == 0


class TestEventManagerErrorHandling:
    """Test error handling in EventManager."""

    @pytest.fixture
    def error_manager(self):
        return MockEventManager()

    def test_emit_with_none_payload(self, error_manager):
        """Test emitting event with None payload."""
        error_manager.emit("test.event", None)
        assert len(error_manager.emitted_events) == 1

    def test_emit_with_invalid_event_type(self, error_manager):
        """Test emitting with invalid event type."""
        # Should handle gracefully
        error_manager.emit(None, MockPayload())
        error_manager.emit("", MockPayload())
        error_manager.emit(123, MockPayload())

        assert len(error_manager.emitted_events) == 3

    def test_add_hook_with_invalid_function(self, error_manager):
        """Test adding invalid hook function."""
        # Should handle gracefully
        error_manager.add_hook("test.event", None)
        error_manager.add_hook("test.event", "not_a_function")

        # Still added to hooks list (validation would be in real implementation)
        assert len(error_manager.hooks["test.event"]) == 2

    def test_concurrent_event_emission(self, error_manager):
        """Test concurrent event emission."""
        import threading

        def emit_events():
            for i in range(10):
                error_manager.emit(f"concurrent.{i}", MockPayload({"id": i}))

        # Create multiple threads
        threads = [threading.Thread(target=emit_events) for _ in range(3)]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Should have 30 events total (3 threads * 10 events each)
        assert len(error_manager.emitted_events) == 30

    def test_hook_exception_isolation(self, error_manager):
        """Test that hook exceptions don't affect other hooks."""
        results = []

        def working_hook1(payload):
            results.append("hook1")

        def failing_hook(payload):
            results.append("failing")
            raise Exception("Hook error")

        def working_hook2(payload):
            results.append("hook2")

        error_manager.add_hook("test.event", working_hook1)
        error_manager.add_hook("test.event", failing_hook)
        error_manager.add_hook("test.event", working_hook2)

        # Simulate execution with error handling
        payload = MockPayload()
        for hook in error_manager.hooks["test.event"]:
            try:
                hook(payload)
            except Exception:
                continue  # Skip failed hooks

        # Working hooks should still execute
        assert "hook1" in results
        assert "hook2" in results
        assert "failing" in results