"""
Enhanced event system for Woodwork engine with typed payloads and component namespacing.

This module provides:
- Type-safe event payloads with runtime validation
- Component context for event attribution 
- Backwards-compatible API
"""

# Core event system - keep existing API
from .events import EventManager, get_global_event_manager, set_global_event_manager, emit, register_hook, register_pipe, create_default_emitter

# New typed payload system - now imported from types
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
    PayloadRegistry
)

# Event source tracking system
from woodwork.types.event_source import EventSource, track_events_from

__all__ = [
    # Core event system
    'EventManager',
    'get_global_event_manager', 
    'set_global_event_manager',
    'emit',
    'register_hook',
    'register_pipe',
    'create_default_emitter',
    
    # Payload types
    'BasePayload',
    'GenericPayload',
    'InputReceivedPayload', 
    'AgentThoughtPayload',
    'AgentActionPayload',
    'ToolCallPayload',
    'ToolObservationPayload',
    'AgentStepCompletePayload',
    'AgentErrorPayload',
    'PayloadRegistry',
    
    # Event source tracking
    'EventSource',
    'track_events_from',
]