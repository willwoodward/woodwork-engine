"""
Simplified in-memory message bus for streaming implementation

This is a basic message bus implementation that handles pub/sub messaging
for streaming data between components. It's designed as a starting point
before the full distributed message bus is implemented.
"""

import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional, Set
from collections import defaultdict
import json
import time
import uuid

log = logging.getLogger(__name__)


class SimpleMessageBus:
    """Simplified in-memory message bus for streaming implementation"""
    
    def __init__(self):
        # Topic-based subscriptions
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Direct component messaging
        self.component_handlers: Dict[str, Callable] = {}
        
        # Message queues for components that aren't immediately available
        self.component_queues: Dict[str, List[Any]] = defaultdict(list)
        
        # Bus state
        self.running = False
        self.message_count = 0
        self.error_count = 0
        
        # Performance tracking
        self.start_time = 0
        self.stats = {
            "messages_published": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "active_subscriptions": 0
        }
        
    async def start(self):
        """Start the message bus"""
        if self.running:
            return
            
        self.running = True
        self.start_time = time.time()
        log.info("Simple message bus started")
        
    async def stop(self):
        """Stop the message bus and clean up resources"""
        self.running = False
        
        # Clear all subscriptions and queues
        self.subscribers.clear()
        self.component_handlers.clear()
        self.component_queues.clear()
        
        log.info("Simple message bus stopped")
        
    async def publish(self, topic: str, data: Any, sender_id: Optional[str] = None):
        """
        Publish message to topic
        
        Args:
            topic: Topic to publish to
            data: Message data
            sender_id: ID of sending component (optional)
        """
        if not self.running:
            log.warning("Message bus not running, dropping message")
            return
            
        self.message_count += 1
        self.stats["messages_published"] += 1
        
        # Create message envelope
        message = {
            "id": f"msg-{uuid.uuid4().hex[:8]}",
            "topic": topic,
            "data": data,
            "sender_id": sender_id,
            "timestamp": time.time()
        }
        
        # Deliver to all subscribers
        delivered_count = 0
        failed_count = 0
        
        subscribers = self.subscribers.get(topic, [])
        log.debug(f"Publishing to {topic}: {len(subscribers)} subscribers")
        
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
                delivered_count += 1
            except Exception as e:
                log.error(f"Error in subscriber callback for {topic}: {e}")
                failed_count += 1
                
        self.stats["messages_delivered"] += delivered_count
        self.stats["messages_failed"] += failed_count
        
        log.debug(f"Published to {topic}: {delivered_count} delivered, {failed_count} failed")
    
    def subscribe(self, topic: str, callback: Callable):
        """
        Subscribe to topic
        
        Args:
            topic: Topic to subscribe to
            callback: Function to call when message received
        """
        self.subscribers[topic].append(callback)
        self.stats["active_subscriptions"] = sum(len(subs) for subs in self.subscribers.values())
        log.debug(f"Subscribed to {topic}, total subscriptions: {self.stats['active_subscriptions']}")
        
    def unsubscribe(self, topic: str, callback: Callable):
        """
        Unsubscribe from topic
        
        Args:
            topic: Topic to unsubscribe from
            callback: Callback function to remove
        """
        if callback in self.subscribers[topic]:
            self.subscribers[topic].remove(callback)
            self.stats["active_subscriptions"] = sum(len(subs) for subs in self.subscribers.values())
            log.debug(f"Unsubscribed from {topic}")
    
    async def send_to_component(self, component_id: str, data: Any, sender_id: Optional[str] = None):
        """
        Send message directly to specific component
        
        Args:
            component_id: Target component ID
            data: Message data  
            sender_id: ID of sending component (optional)
        """
        if not self.running:
            return
            
        message = {
            "id": f"msg-{uuid.uuid4().hex[:8]}",
            "target": component_id,
            "data": data,
            "sender_id": sender_id,
            "timestamp": time.time()
        }
        
        # Try to deliver directly if handler exists
        if component_id in self.component_handlers:
            try:
                handler = self.component_handlers[component_id]
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
                log.debug(f"Sent direct message to {component_id}")
            except Exception as e:
                log.error(f"Error delivering message to {component_id}: {e}")
        else:
            # Queue message for when component becomes available
            self.component_queues[component_id].append(message)
            log.debug(f"Queued message for {component_id}")
    
    def register_component_handler(self, component_id: str, handler: Callable):
        """
        Register handler for direct component messaging
        
        Args:
            component_id: Component ID
            handler: Function to handle messages for this component
        """
        self.component_handlers[component_id] = handler
        
        # Deliver any queued messages
        queued_messages = self.component_queues[component_id]
        if queued_messages:
            log.debug(f"Delivering {len(queued_messages)} queued messages to {component_id}")
            asyncio.create_task(self._deliver_queued_messages(component_id, queued_messages))
            self.component_queues[component_id] = []
            
        log.debug(f"Registered component handler: {component_id}")
    
    def unregister_component_handler(self, component_id: str):
        """
        Unregister component handler
        
        Args:
            component_id: Component ID to unregister
        """
        if component_id in self.component_handlers:
            del self.component_handlers[component_id]
            log.debug(f"Unregistered component handler: {component_id}")
    
    async def _deliver_queued_messages(self, component_id: str, messages: List[Any]):
        """Deliver queued messages to component"""
        handler = self.component_handlers.get(component_id)
        if not handler:
            return
            
        for message in messages:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                log.error(f"Error delivering queued message to {component_id}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get message bus statistics"""
        uptime = time.time() - self.start_time if self.running else 0
        
        return {
            "running": self.running,
            "uptime_seconds": uptime,
            "total_messages": self.message_count,
            "messages_per_second": self.message_count / max(uptime, 1),
            "active_topics": len(self.subscribers),
            "registered_components": len(self.component_handlers),
            "queued_messages": sum(len(queue) for queue in self.component_queues.values()),
            **self.stats
        }
    
    def get_topics(self) -> List[str]:
        """Get list of active topics"""
        return list(self.subscribers.keys())
    
    def get_components(self) -> List[str]:
        """Get list of registered components"""
        return list(self.component_handlers.keys())
    
    def clear_topic(self, topic: str):
        """Remove all subscribers from a topic"""
        if topic in self.subscribers:
            del self.subscribers[topic]
            self.stats["active_subscriptions"] = sum(len(subs) for subs in self.subscribers.values())
            log.debug(f"Cleared topic: {topic}")


# Convenience functions for streaming integration
async def setup_streaming_topics(message_bus: SimpleMessageBus):
    """Setup standard topics for streaming"""
    streaming_topics = [
        "stream.created",
        "stream.chunk", 
        "stream.completed",
        "stream.failed",
        "stream.chunk_missing",
        "component.heartbeat"
    ]
    
    for topic in streaming_topics:
        # Topics are created implicitly when first subscriber is added
        log.debug(f"Streaming topic available: {topic}")


class MessageBusAdapter:
    """Adapter to provide higher-level interface for components"""
    
    def __init__(self, message_bus: SimpleMessageBus):
        self.message_bus = message_bus
        self._subscription_callbacks: Dict[str, Callable] = {}
    
    async def emit_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        component_source: Optional[str] = None
    ):
        """Emit event through message bus"""
        event_data = {
            "event_type": event_type,
            "payload": payload,
            "session_id": session_id,
            "component_source": component_source
        }
        
        await self.message_bus.publish(event_type, event_data, component_source)
    
    def register_hook(self, event_pattern: str, handler: Callable, component_id: Optional[str] = None):
        """Register hook for events matching pattern"""
        
        async def wrapped_handler(message):
            try:
                event_data = message.get("data", {})
                await handler(event_data)
            except Exception as e:
                log.error(f"Hook handler error for {event_pattern}: {e}")
        
        self.message_bus.subscribe(event_pattern, wrapped_handler)
        
        # Store reference for cleanup
        callback_key = f"{event_pattern}:{component_id or 'global'}"
        self._subscription_callbacks[callback_key] = wrapped_handler
    
    def register_component_listener(self, component_id: str, handler: Callable):
        """Register component to receive targeted messages"""
        
        async def wrapped_handler(message):
            try:
                await handler(message.get("data", {}))
            except Exception as e:
                log.error(f"Component handler error for {component_id}: {e}")
        
        self.message_bus.register_component_handler(component_id, wrapped_handler)
    
    async def send_to_component(
        self,
        target_component: str,
        event_type: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        component_source: Optional[str] = None
    ):
        """Send message directly to specific component"""
        message_data = {
            "event_type": event_type,
            "payload": payload,
            "session_id": session_id,
            "component_source": component_source
        }
        
        await self.message_bus.send_to_component(target_component, message_data, component_source)
    
    async def close(self):
        """Cleanup adapter resources"""
        # Remove all our subscriptions
        for callback in self._subscription_callbacks.values():
            # Note: We'd need to track topic->callback mapping to properly unsubscribe
            # For now, the message bus cleanup will handle this
            pass
        
        self._subscription_callbacks.clear()


# Global message bus instance for convenience
_global_message_bus: Optional[SimpleMessageBus] = None


async def get_global_message_bus() -> SimpleMessageBus:
    """Get or create global message bus instance"""
    global _global_message_bus
    if _global_message_bus is None:
        _global_message_bus = SimpleMessageBus()
        await _global_message_bus.start()
    return _global_message_bus


def set_global_message_bus(message_bus: SimpleMessageBus):
    """Set global message bus instance"""
    global _global_message_bus
    _global_message_bus = message_bus