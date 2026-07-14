"""Tests for TraceCollector, TraceEvent, and Trace."""

from unittest.mock import MagicMock
from collections import defaultdict

from woodwork.eval.trace import TraceCollector, TraceEvent, Trace
from woodwork.types.events import AgentThoughtPayload, ToolCallPayload


class TestTraceEvent:
    def test_creation(self):
        event = TraceEvent(event_type="agent.thought", timestamp=1.0, data={"thought": "hello"})
        assert event.event_type == "agent.thought"
        assert event.timestamp == 1.0
        assert event.data == {"thought": "hello"}


class TestTrace:
    def test_creation(self):
        events = [TraceEvent(event_type="agent.thought", timestamp=1.0, data={"thought": "thinking"})]
        trace = Trace(events=events, response="final answer", duration_seconds=2.5)
        assert len(trace.events) == 1
        assert trace.response == "final answer"
        assert trace.duration_seconds == 2.5


class TestTraceCollector:
    def _make_event_bus(self):
        """Create a mock event bus with hook registration."""
        bus = MagicMock()
        bus._hooks = defaultdict(list)

        def register_hook(event_type, hook):
            bus._hooks[event_type].append(hook)

        bus.register_hook = register_hook
        return bus

    def test_register_hooks(self):
        bus = self._make_event_bus()
        collector = TraceCollector()
        collector.register(bus)
        for event_type in TraceCollector.ALL_EVENTS:
            assert len(bus._hooks[event_type]) == 1

    def test_capture_typed_payload(self):
        bus = self._make_event_bus()
        collector = TraceCollector()
        collector.register(bus)

        # Simulate an event by calling the hook directly
        hook = bus._hooks["agent.thought"][0]
        payload = AgentThoughtPayload(thought="I should search")
        hook(payload)

        assert len(collector._events) == 1
        assert collector._events[0].event_type == "agent.thought"
        assert collector._events[0].data["thought"] == "I should search"

    def test_capture_dict_payload(self):
        bus = self._make_event_bus()
        collector = TraceCollector()
        collector.register(bus)

        hook = bus._hooks["tool.call"][0]
        hook({"tool": "search", "args": {"q": "hello"}})

        assert len(collector._events) == 1
        assert collector._events[0].data["tool"] == "search"

    def test_reset(self):
        bus = self._make_event_bus()
        collector = TraceCollector()
        collector.register(bus)

        hook = bus._hooks["agent.thought"][0]
        hook(AgentThoughtPayload(thought="first"))
        assert len(collector._events) == 1

        collector.reset()
        assert len(collector._events) == 0

    def test_get_trace(self):
        bus = self._make_event_bus()
        collector = TraceCollector()
        collector.register(bus)

        hook = bus._hooks["tool.call"][0]
        hook(ToolCallPayload(tool="search", args={"q": "test"}))

        trace = collector.get_trace("the answer", 1.5)
        assert isinstance(trace, Trace)
        assert trace.response == "the answer"
        assert trace.duration_seconds == 1.5
        assert len(trace.events) == 1

    def test_unregister(self):
        bus = self._make_event_bus()
        collector = TraceCollector()
        collector.register(bus)
        assert len(bus._hooks["agent.thought"]) == 1

        collector.unregister(bus)
        assert len(bus._hooks["agent.thought"]) == 0

    def test_events_are_copied_in_get_trace(self):
        """get_trace should return a snapshot, not a reference to the internal list."""
        bus = self._make_event_bus()
        collector = TraceCollector()
        collector.register(bus)

        hook = bus._hooks["agent.thought"][0]
        hook(AgentThoughtPayload(thought="one"))
        trace = collector.get_trace("answer", 1.0)

        # Adding more events shouldn't affect the returned trace
        hook(AgentThoughtPayload(thought="two"))
        assert len(trace.events) == 1
        assert len(collector._events) == 2
