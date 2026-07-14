"""Trace capture for eval runs — hooks into the event bus to record all events."""

import time
from dataclasses import dataclass

from woodwork.types.events import BasePayload


@dataclass
class TraceEvent:
    """A single event captured during an eval run."""

    event_type: str
    timestamp: float
    data: dict


@dataclass
class Trace:
    """Complete trace of a single eval case execution."""

    events: list[TraceEvent]
    response: str
    duration_seconds: float


class TraceCollector:
    """Registers hooks on all event types, accumulates TraceEvents."""

    ALL_EVENTS = [
        "input.received",
        "agent.thought",
        "agent.action",
        "tool.call",
        "tool.observation",
        "agent.step_complete",
        "agent.error",
    ]

    def __init__(self):
        self._events: list[TraceEvent] = []
        self._hooks: list[tuple[str, object]] = []

    def _make_hook(self, event_type: str):
        """Create a hook function for a specific event type."""

        def hook(payload):
            data: dict
            if isinstance(payload, BasePayload):
                data = payload.to_dict()
            elif isinstance(payload, dict):
                data = payload
            else:
                data = dict(vars(payload)) if hasattr(payload, "__dict__") else {"raw": str(payload)}
            self._events.append(TraceEvent(event_type=event_type, timestamp=time.time(), data=data))

        return hook

    def register(self, event_bus) -> None:
        """Register hooks on the event bus for all tracked event types."""
        for event_type in self.ALL_EVENTS:
            hook = self._make_hook(event_type)
            event_bus.register_hook(event_type, hook)
            self._hooks.append((event_type, hook))

    def reset(self) -> None:
        """Clear captured events for the next case."""
        self._events.clear()

    def get_trace(self, response: str, duration: float) -> Trace:
        """Build a Trace from captured events."""
        return Trace(events=list(self._events), response=response, duration_seconds=duration)

    def unregister(self, event_bus) -> None:
        """Remove hooks from the event bus."""
        for event_type, hook in self._hooks:
            hooks_list = event_bus._hooks.get(event_type, [])
            if hook in hooks_list:
                hooks_list.remove(hook)
        self._hooks.clear()
