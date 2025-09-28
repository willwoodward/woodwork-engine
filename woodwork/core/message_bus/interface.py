"""
Core Message Bus Interfaces

Defines the abstract interface and data structures for the distributed message bus
that replaces centralized Task Master orchestration.
"""

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
import logging

log = logging.getLogger(__name__)


class MessageDeliveryMode(Enum):
    """Message delivery guarantees"""
    AT_MOST_ONCE = "at_most_once"        # Fire and forget
    AT_LEAST_ONCE = "at_least_once"      # Guaranteed delivery with possible duplicates
    EXACTLY_ONCE = "exactly_once"        # Guaranteed single delivery (future)


class MessagePattern(Enum):
    """Message routing patterns"""
    POINT_TO_POINT = "point_to_point"    # Direct component messaging
    PUBLISH_SUBSCRIBE = "publish_subscribe" # Hook broadcasting


@dataclass
class MessageEnvelope:
    """Message envelope with metadata and delivery guarantees"""
    message_id: str
    session_id: str
    event_type: str
    payload: Dict[str, Any]
    sender_component: Optional[str] = None
    target_component: Optional[str] = None
    delivery_mode: MessageDeliveryMode = MessageDeliveryMode.AT_LEAST_ONCE
    pattern: MessagePattern = MessagePattern.POINT_TO_POINT
    created_at: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3
    ttl_seconds: Optional[int] = 300  # 5 minutes default
    
    def __post_init__(self):
        """Validate message envelope"""
        if not self.message_id:
            self.message_id = f"msg-{uuid.uuid4().hex[:12]}"
        
        if not self.session_id:
            raise ValueError("session_id is required")
        
        if not self.event_type:
            raise ValueError("event_type is required")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transport"""
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "sender_component": self.sender_component,
            "target_component": self.target_component,
            "delivery_mode": self.delivery_mode.value,
            "pattern": self.pattern.value,
            "created_at": self.created_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "ttl_seconds": self.ttl_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageEnvelope':
        """Deserialize from transport"""
        return cls(
            message_id=data["message_id"],
            session_id=data["session_id"],
            event_type=data["event_type"],
            payload=data["payload"],
            sender_component=data.get("sender_component"),
            target_component=data.get("target_component"),
            delivery_mode=MessageDeliveryMode(data.get("delivery_mode", "at_least_once")),
            pattern=MessagePattern(data.get("pattern", "point_to_point")),
            created_at=data.get("created_at", time.time()),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            ttl_seconds=data.get("ttl_seconds", 300)
        )
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        if self.ttl_seconds is None:
            return False
        return time.time() - self.created_at > self.ttl_seconds
    
    def can_retry(self) -> bool:
        """Check if message can be retried"""
        return self.retry_count < self.max_retries and not self.is_expired()


class MessageBusInterface(ABC):
    """Abstract interface for message bus implementations"""
    
    @abstractmethod
    async def start(self) -> None:
        """Start the message bus"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the message bus and cleanup resources"""
        pass
    
    @abstractmethod
    async def publish(self, envelope: MessageEnvelope) -> bool:
        """
        Publish message to topic (pub/sub pattern)
        
        Args:
            envelope: Message envelope to publish
            
        Returns:
            True if published successfully
        """
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, callback: Callable[[MessageEnvelope], None]) -> str:
        """
        Subscribe to topic
        
        Args:
            topic: Topic to subscribe to
            callback: Function to call when message received
            
        Returns:
            Subscription ID for unsubscribing
        """
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from topic
        
        Args:
            subscription_id: Subscription ID returned by subscribe()
            
        Returns:
            True if unsubscribed successfully
        """
        pass
    
    @abstractmethod
    async def send_to_component(self, envelope: MessageEnvelope) -> bool:
        """
        Send message directly to component (point-to-point pattern)
        
        Args:
            envelope: Message envelope with target_component set
            
        Returns:
            True if sent successfully
        """
        pass
    
    @abstractmethod
    def register_component_handler(self, component_id: str, handler: Callable[[MessageEnvelope], None]) -> None:
        """
        Register handler for direct component messaging
        
        Args:
            component_id: Component ID to register
            handler: Function to handle messages for this component
        """
        pass
    
    @abstractmethod
    def unregister_component_handler(self, component_id: str) -> bool:
        """
        Unregister component handler
        
        Args:
            component_id: Component ID to unregister
            
        Returns:
            True if unregistered successfully
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics"""
        pass
    
    @abstractmethod
    def is_healthy(self) -> bool:
        """Check if message bus is healthy"""
        pass


# Utility functions for creating message envelopes
def create_component_message(
    session_id: str,
    event_type: str,
    payload: Dict[str, Any],
    target_component: str,
    sender_component: Optional[str] = None,
    delivery_mode: MessageDeliveryMode = MessageDeliveryMode.AT_LEAST_ONCE
) -> MessageEnvelope:
    """Create a point-to-point component message"""
    
    log.debug(f"[MessageBus] Creating component message: {sender_component} -> {target_component}, event: {event_type}")
    
    return MessageEnvelope(
        message_id=f"msg-{uuid.uuid4().hex[:12]}",
        session_id=session_id,
        event_type=event_type,
        payload=payload,
        sender_component=sender_component,
        target_component=target_component,
        delivery_mode=delivery_mode,
        pattern=MessagePattern.POINT_TO_POINT
    )


def create_hook_message(
    session_id: str,
    event_type: str,
    payload: Dict[str, Any],
    sender_component: Optional[str] = None,
    delivery_mode: MessageDeliveryMode = MessageDeliveryMode.AT_MOST_ONCE
) -> MessageEnvelope:
    """Create a pub/sub hook message"""
    
    log.debug(f"[MessageBus] Creating hook message from {sender_component}, event: {event_type}")
    
    return MessageEnvelope(
        message_id=f"hook-{uuid.uuid4().hex[:12]}",
        session_id=session_id,
        event_type=event_type,
        payload=payload,
        sender_component=sender_component,
        target_component=None,
        delivery_mode=delivery_mode,
        pattern=MessagePattern.PUBLISH_SUBSCRIBE
    )