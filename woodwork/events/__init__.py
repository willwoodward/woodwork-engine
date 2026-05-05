"""
Event system for Woodwork engine with typed payloads and component namespacing.

The canonical event system is the UnifiedEventBus (woodwork.runtime.unified_event_bus).
This module provides backward-compatible public API that delegates to it.
"""

# Backward-compatible imports from legacy EventManager (still used for create_default_emitter)
from .events import (
    EventManager,
    get_global_event_manager,
    set_global_event_manager,
    emit,
    register_hook,
    register_pipe,
    create_default_emitter,
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
    # Core event system (delegates to UnifiedEventBus)
    "EventManager",
    "get_global_event_manager",
    "set_global_event_manager",
    "emit",
    "register_hook",
    "register_pipe",
    "create_default_emitter",
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
