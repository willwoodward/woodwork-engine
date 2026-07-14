"""
Event system for Woodwork engine.

Re-exports both the new per-agent EventBus (woodwork.core.events) and
the typed payload helpers from woodwork.types.events.
"""

from woodwork.core.events import EventBus

# Typed payload system (unchanged)
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
    "EventBus",
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
