"""
Event system for Woodwork engine with typed payloads.

The canonical event system is the UnifiedEventBus (woodwork.runtime.unified_event_bus).
This module re-exports its public API.
"""

from woodwork.runtime.unified_event_bus import (
    get_global_event_bus,
    set_global_event_bus,
    emit,
    emit_sync,
    register_hook,
    register_pipe,
    register_component,
)

# Typed payload system
from woodwork.types.events import (
    BasePayload,
    GenericPayload,
    InputReceivedPayload,
    AgentThoughtPayload,
    AgentActionPayload,
    ToolCallPayload,
    ToolObservationPayload,
    AgentStepCompletePayload,
    AgentErrorPayload,
    PayloadRegistry,
)

# Event source tracking system
from woodwork.types.event_source import EventSource, track_events_from

__all__ = [
    # Core event system
    "get_global_event_bus",
    "set_global_event_bus",
    "emit",
    "emit_sync",
    "register_hook",
    "register_pipe",
    "register_component",
    # Payload types
    "BasePayload",
    "GenericPayload",
    "InputReceivedPayload",
    "AgentThoughtPayload",
    "AgentActionPayload",
    "ToolCallPayload",
    "ToolObservationPayload",
    "AgentStepCompletePayload",
    "AgentErrorPayload",
    "PayloadRegistry",
    # Event source tracking
    "EventSource",
    "track_events_from",
]
