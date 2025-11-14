"""Unit tests for component lifecycle functions.

Tests the simplified start_component function to ensure
components are started correctly in parallel.
"""

import pytest
import queue
from unittest.mock import Mock
from woodwork.cli.progress.lifecycles import start_component
from woodwork.interfaces.startable import Startable
from woodwork.types import Update


class MockStartableComponent(Startable):
    """Mock component implementing Startable interface."""

    def __init__(self, name):
        self.name = name
        self.started = False
        self.start_called_with = None

    def start(self, queue=None, config=None):
        """Mock start method."""
        self.started = True
        self.start_called_with = (queue, config)
        if queue:
            queue.put(Update(progress=40, component_name=self.name))


class MockNonStartableComponent:
    """Mock component not implementing Startable interface."""

    def __init__(self, name):
        self.name = name


class TestStartComponent:
    """Test the start_component function."""

    def test_startable_component_calls_start(self):
        """Test that Startable components have their start() method called."""
        component = MockStartableComponent(name="test_comp")
        q = queue.Queue()

        start_component(component, q)

        assert component.started is True
        assert component.start_called_with == (q, {})

    def test_startable_component_reports_progress(self):
        """Test that Startable components report progress correctly."""
        component = MockStartableComponent(name="test_comp")
        q = queue.Queue()

        start_component(component, q)

        # Should get progress updates: 40% from component, 50% from lifecycle
        updates = []
        while not q.empty():
            updates.append(q.get())

        assert len(updates) == 2
        assert updates[0].progress == 40
        assert updates[0].component_name == "test_comp"
        assert updates[1].progress == 50
        assert updates[1].component_name == "test_comp"

    def test_non_startable_component_skips_start(self):
        """Test that non-Startable components skip start() and report 100%."""
        component = MockNonStartableComponent(name="test_comp")
        q = queue.Queue()

        start_component(component, q)

        # Should only get 100% progress
        updates = []
        while not q.empty():
            updates.append(q.get())

        assert len(updates) == 1
        assert updates[0].progress == 100
        assert updates[0].component_name == "test_comp"

    def test_component_without_queue(self):
        """Test that components work even without a queue."""
        component = MockStartableComponent(name="test_comp")

        # Should not raise an error
        start_component(component, None)

        assert component.started is True

    def test_multiple_components_in_sequence(self):
        """Test starting multiple components in sequence."""
        components = [
            MockStartableComponent(name="comp1"),
            MockNonStartableComponent(name="comp2"),
            MockStartableComponent(name="comp3"),
        ]
        q = queue.Queue()

        for comp in components:
            start_component(comp, q)

        # Verify progress updates
        updates = []
        while not q.empty():
            updates.append(q.get())

        # comp1: 40%, 50%; comp2: 100%; comp3: 40%, 50%
        assert len(updates) == 5

        # Check comp1 updates
        assert updates[0].component_name == "comp1"
        assert updates[0].progress == 40
        assert updates[1].component_name == "comp1"
        assert updates[1].progress == 50

        # Check comp2 update
        assert updates[2].component_name == "comp2"
        assert updates[2].progress == 100

        # Check comp3 updates
        assert updates[3].component_name == "comp3"
        assert updates[3].progress == 40
        assert updates[4].component_name == "comp3"
        assert updates[4].progress == 50


class TestStartComponentErrorHandling:
    """Test error handling in start_component."""

    def test_component_start_raises_exception(self):
        """Test that exceptions in start() propagate correctly."""
        component = MockStartableComponent(name="failing_comp")
        q = queue.Queue()

        # Override start to raise an exception
        def failing_start(queue=None, config=None):
            raise RuntimeError("Component failed to start")

        component.start = failing_start

        with pytest.raises(RuntimeError, match="Component failed to start"):
            start_component(component, q)

    def test_component_with_invalid_name(self):
        """Test component without name attribute."""
        component = Mock(spec=Startable)
        component.start = Mock()
        # No name attribute
        q = queue.Queue()

        with pytest.raises(AttributeError):
            start_component(component, q)


class TestIntegrationWithProgress:
    """Integration tests with the progress bar system."""

    def test_parallel_execution_simulation(self):
        """Simulate parallel execution of multiple components."""
        import threading

        components = [MockStartableComponent(name=f"comp{i}") for i in range(5)]
        q = queue.Queue()
        threads = []

        # Start all components in parallel (simulated)
        for comp in components:
            t = threading.Thread(target=start_component, args=(comp, q))
            t.start()
            threads.append(t)

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify all components started
        for comp in components:
            assert comp.started is True

        # Verify all progress updates received
        updates = []
        while not q.empty():
            updates.append(q.get())

        # Each component should report 2 updates (40% and 50%)
        assert len(updates) == 10
        component_names = [u.component_name for u in updates]
        for comp in components:
            assert component_names.count(comp.name) == 2
