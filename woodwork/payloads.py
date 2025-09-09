"""
Convenience module for event payload types.

This module provides easy imports for all event payload types that can be used
in pipes, hooks, and custom event handling code.

Example usage:
    from woodwork.payloads import InputReceivedPayload, AgentThoughtPayload, ToolCallPayload
    
    def my_pipe(payload):
        if isinstance(payload, InputReceivedPayload):
            # Access typed fields directly
            print(f"Input from {payload.component_id}: {payload.input}")
        elif isinstance(payload, ToolCallPayload):
            print(f"Tool call: {payload.tool} with args {payload.args}")
        return payload
"""

# Re-export all payload types for easy importing - now from types module
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

from woodwork.types.event_source import EventSource, track_events_from

__all__ = [
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
    'EventSource',
    'track_events_from',
]