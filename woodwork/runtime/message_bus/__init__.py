"""
Distributed Message Bus for Woodwork Components

This module provides the message bus abstraction that replaces the centralized
Task Master with distributed component communication while preserving declarative
routing via the 'to:' property.

Key Features:
- Seamless integration with existing event system
- Zero-configuration component-to-component communication
- Declarative routing based on .ww configuration
- Support for multiple backends (in-memory, Redis, NATS)
"""

from .interface import MessageBusInterface, MessageEnvelope, MessageDeliveryMode, MessagePattern
from .in_memory_bus import InMemoryMessageBus
from .factory import MessageBusFactory, create_default_message_bus, get_global_message_bus, set_global_message_bus
from .integration import MessageBusIntegration
from .errors import StreamingChunk, ComponentNotFoundError, ResponseTimeoutError, ComponentError
from .builder import MessageBuilder, RequestContext
from .manager import (
    GlobalMessageBusManager,
    get_global_message_bus_manager,
    register_component_with_message_bus,
    initialize_global_message_bus_integration,
)

__all__ = [
    # Core interfaces
    "MessageBusInterface",
    "MessageEnvelope",
    "MessageDeliveryMode",
    "MessagePattern",
    # Implementations
    "InMemoryMessageBus",
    # Factory and globals
    "MessageBusFactory",
    "create_default_message_bus",
    "get_global_message_bus",
    "set_global_message_bus",
    # Integration
    "MessageBusIntegration",
    # Errors
    "StreamingChunk",
    "ComponentNotFoundError",
    "ResponseTimeoutError",
    "ComponentError",
    # Builder
    "MessageBuilder",
    "RequestContext",
    # Manager
    "GlobalMessageBusManager",
    "get_global_message_bus_manager",
    "register_component_with_message_bus",
    "initialize_global_message_bus_integration",
]
