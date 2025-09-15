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
from .declarative_router import DeclarativeRouter
from .integration import MessageBusIntegration

__all__ = [
    # Core interfaces
    'MessageBusInterface',
    'MessageEnvelope', 
    'MessageDeliveryMode',
    'MessagePattern',
    
    # Implementations
    'InMemoryMessageBus',
    
    # Factory and globals
    'MessageBusFactory',
    'create_default_message_bus',
    'get_global_message_bus',
    'set_global_message_bus',
    
    # Routing
    'DeclarativeRouter',
    
    # Integration
    'MessageBusIntegration',
]