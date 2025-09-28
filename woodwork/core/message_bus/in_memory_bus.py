"""
In-Memory Message Bus Implementation

Provides a high-performance, feature-complete message bus for local development
and single-process deployments. Includes all enterprise features like retry logic,
dead letter queues, and comprehensive monitoring.
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from typing import Dict, List, Callable, Any, Optional, Set
from dataclasses import dataclass

from .interface import MessageBusInterface, MessageEnvelope, MessageDeliveryMode, MessagePattern

log = logging.getLogger(__name__)


@dataclass
class Subscription:
    """Internal subscription tracking"""
    subscription_id: str
    topic: str
    callback: Callable[[MessageEnvelope], None]
    created_at: float
    message_count: int = 0


@dataclass
class ComponentHandler:
    """Internal component handler tracking"""
    component_id: str
    handler: Callable[[MessageEnvelope], None]
    registered_at: float
    message_count: int = 0
    last_message_at: Optional[float] = None


class InMemoryMessageBus(MessageBusInterface):
    """
    High-performance in-memory message bus with enterprise features
    
    Features:
    - Topic-based pub/sub for hooks
    - Direct component-to-component messaging  
    - Retry logic with exponential backoff
    - Dead letter queue for failed messages
    - Comprehensive metrics and monitoring
    - Session isolation
    """
    
    def __init__(self, max_queue_size: int = 10000, max_retries: int = 3):
        self.max_queue_size = max_queue_size
        self.max_retries = max_retries
        
        # Core messaging structures
        self.subscriptions: Dict[str, Subscription] = {}
        self.topic_subscribers: Dict[str, Set[str]] = defaultdict(set)  # topic -> subscription_ids
        self.component_handlers: Dict[str, ComponentHandler] = {}
        
        # Message queues
        self.component_queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_queue_size))
        self.dead_letter_queue: deque = deque(maxlen=1000)
        self.retry_queue: List[MessageEnvelope] = []
        
        # State management
        self.running = False
        self.start_time = 0.0
        
        # Background tasks
        self._retry_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Comprehensive statistics
        self.stats = {
            # Message counts
            "messages_published": 0,
            "messages_delivered": 0,
            "messages_failed": 0,
            "messages_retried": 0,
            "messages_dead_lettered": 0,
            
            # Component stats  
            "active_subscriptions": 0,
            "registered_components": 0,
            "queued_messages": 0,
            
            # Performance stats
            "avg_delivery_time_ms": 0.0,
            "peak_queue_size": 0,
            
            # Error stats
            "delivery_failures": 0,
            "timeout_failures": 0,
            "retry_exhausted": 0
        }
        
        log.debug("[InMemoryMessageBus] Initialized with max_queue_size=%d, max_retries=%d", 
                  max_queue_size, max_retries)
    
    async def start(self) -> None:
        """Start the message bus with background tasks"""
        if self.running:
            log.debug("[InMemoryMessageBus] Already running")
            return
            
        self.running = True
        self.start_time = time.time()
        
        # Start background retry processing
        self._retry_task = asyncio.create_task(self._retry_processor())
        self._retry_task.set_name("message_bus_retry_processor")
        
        # Start background cleanup
        self._cleanup_task = asyncio.create_task(self._cleanup_processor()) 
        self._cleanup_task.set_name("message_bus_cleanup")
        
        log.info("[InMemoryMessageBus] Started with retry processing and cleanup tasks")
    
    async def stop(self) -> None:
        """Stop the message bus and cleanup resources"""
        if not self.running:
            log.debug("[InMemoryMessageBus] Already stopped")
            return
            
        self.running = False
        
        # Cancel background tasks
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clear all data structures
        self.subscriptions.clear()
        self.topic_subscribers.clear()
        self.component_handlers.clear()
        self.component_queues.clear()
        self.retry_queue.clear()
        
        uptime = time.time() - self.start_time
        log.info("[InMemoryMessageBus] Stopped after %.2f seconds. Final stats: %s", 
                 uptime, self.get_stats())
    
    async def publish(self, envelope: MessageEnvelope) -> bool:
        """Publish message to topic subscribers (pub/sub pattern)"""
        if not self.running:
            log.warning("[InMemoryMessageBus] Not running, dropping publish message: %s", envelope.event_type)
            return False
            
        start_time = time.time()
        delivered_count = 0
        failed_count = 0
        
        # Get subscribers for this topic
        topic = envelope.event_type
        subscriber_ids = self.topic_subscribers.get(topic, set())
        
        log.debug("[InMemoryMessageBus] Publishing '%s' to %d subscribers (session: %s)", 
                  topic, len(subscriber_ids), envelope.session_id)
        
        # Deliver to each subscriber
        for sub_id in subscriber_ids:
            subscription = self.subscriptions.get(sub_id)
            if not subscription:
                log.warning("[InMemoryMessageBus] Subscription %s not found for topic %s", sub_id, topic)
                continue
                
            try:
                # Execute callback
                if asyncio.iscoroutinefunction(subscription.callback):
                    await subscription.callback(envelope)
                else:
                    subscription.callback(envelope)
                
                subscription.message_count += 1
                delivered_count += 1
                
                log.debug("[InMemoryMessageBus] Delivered to subscription %s", sub_id)
                
            except Exception as e:
                log.error("[InMemoryMessageBus] Failed to deliver to subscription %s: %s", sub_id, e)
                failed_count += 1
                self.stats["delivery_failures"] += 1
        
        # Update statistics
        self.stats["messages_published"] += 1
        self.stats["messages_delivered"] += delivered_count
        self.stats["messages_failed"] += failed_count
        
        delivery_time_ms = (time.time() - start_time) * 1000
        self._update_avg_delivery_time(delivery_time_ms)
        
        log.debug("[InMemoryMessageBus] Published '%s': %d delivered, %d failed in %.2fms", 
                  topic, delivered_count, failed_count, delivery_time_ms)
        
        return failed_count == 0
    
    async def subscribe(self, topic: str, callback: Callable[[MessageEnvelope], None]) -> str:
        """Subscribe to topic with automatic callback execution"""
        subscription_id = f"sub-{uuid.uuid4().hex[:8]}"
        
        subscription = Subscription(
            subscription_id=subscription_id,
            topic=topic,
            callback=callback,
            created_at=time.time()
        )
        
        self.subscriptions[subscription_id] = subscription
        self.topic_subscribers[topic].add(subscription_id)
        self.stats["active_subscriptions"] = len(self.subscriptions)
        
        log.debug("[InMemoryMessageBus] Subscribed %s to topic '%s'. Total subscriptions: %d", 
                  subscription_id, topic, self.stats["active_subscriptions"])
        
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Remove subscription"""
        subscription = self.subscriptions.get(subscription_id)
        if not subscription:
            log.warning("[InMemoryMessageBus] Subscription %s not found for unsubscribe", subscription_id)
            return False
            
        # Remove from topic subscribers
        self.topic_subscribers[subscription.topic].discard(subscription_id)
        if not self.topic_subscribers[subscription.topic]:
            del self.topic_subscribers[subscription.topic]
        
        # Remove subscription
        del self.subscriptions[subscription_id]
        self.stats["active_subscriptions"] = len(self.subscriptions)
        
        log.debug("[InMemoryMessageBus] Unsubscribed %s from topic '%s'. Messages processed: %d", 
                  subscription_id, subscription.topic, subscription.message_count)
        
        return True
    
    async def send_to_component(self, envelope: MessageEnvelope) -> bool:
        """Send message directly to component (point-to-point pattern)"""
        if not self.running:
            log.warning("[InMemoryMessageBus] Not running, dropping component message: %s -> %s", 
                       envelope.sender_component, envelope.target_component)
            return False
            
        if not envelope.target_component:
            log.error("[InMemoryMessageBus] Missing target_component in envelope")
            return False
        
        start_time = time.time()
        
        log.debug("[InMemoryMessageBus] Sending '%s' from %s to %s (session: %s)", 
                  envelope.event_type, envelope.sender_component, 
                  envelope.target_component, envelope.session_id)
        
        # Try direct delivery if handler exists
        handler = self.component_handlers.get(envelope.target_component)
        if handler:
            try:
                # Execute handler
                if asyncio.iscoroutinefunction(handler.handler):
                    await handler.handler(envelope)
                else:
                    handler.handler(envelope)
                
                # Update handler stats
                handler.message_count += 1
                handler.last_message_at = time.time()
                
                # Update message bus stats
                self.stats["messages_delivered"] += 1
                delivery_time_ms = (time.time() - start_time) * 1000
                self._update_avg_delivery_time(delivery_time_ms)
                
                log.debug("[InMemoryMessageBus] Delivered to %s in %.2fms", 
                          envelope.target_component, delivery_time_ms)
                
                return True
                
            except Exception as e:
                log.error("[InMemoryMessageBus] Handler failed for %s: %s", envelope.target_component, e)
                self.stats["delivery_failures"] += 1
                
                # Queue for retry if eligible
                if envelope.can_retry():
                    envelope.retry_count += 1
                    self.retry_queue.append(envelope)
                    self.stats["messages_retried"] += 1
                    log.debug("[InMemoryMessageBus] Queued for retry %d/%d: %s", 
                              envelope.retry_count, envelope.max_retries, envelope.message_id)
                else:
                    self._dead_letter(envelope, f"Handler exception: {e}")
                
                return False
        else:
            # Queue message for when component becomes available
            queue = self.component_queues[envelope.target_component]
            
            if len(queue) >= self.max_queue_size:
                log.warning("[InMemoryMessageBus] Queue full for %s, dropping message", envelope.target_component)
                self._dead_letter(envelope, "Queue full")
                return False
            
            queue.append(envelope)
            self.stats["queued_messages"] = sum(len(q) for q in self.component_queues.values())
            self.stats["peak_queue_size"] = max(self.stats["peak_queue_size"], len(queue))
            
            log.debug("[InMemoryMessageBus] Queued message for %s (queue size: %d)", 
                      envelope.target_component, len(queue))
            
            return True
    
    def register_component_handler(self, component_id: str, handler: Callable[[MessageEnvelope], None]) -> None:
        """Register handler for direct component messaging"""
        handler_obj = ComponentHandler(
            component_id=component_id,
            handler=handler,
            registered_at=time.time()
        )
        
        self.component_handlers[component_id] = handler_obj
        self.stats["registered_components"] = len(self.component_handlers)
        
        # Deliver any queued messages
        queued_messages = list(self.component_queues[component_id])
        if queued_messages:
            self.component_queues[component_id].clear()
            
            log.debug("[InMemoryMessageBus] Delivering %d queued messages to %s", 
                      len(queued_messages), component_id)
            
            # Schedule delivery in background
            asyncio.create_task(self._deliver_queued_messages(component_id, queued_messages))
        
        log.debug("[InMemoryMessageBus] Registered component handler: %s", component_id)
    
    def unregister_component_handler(self, component_id: str) -> bool:
        """Unregister component handler"""
        handler = self.component_handlers.get(component_id)
        if not handler:
            log.warning("[InMemoryMessageBus] Component handler %s not found for unregister", component_id)
            return False
            
        del self.component_handlers[component_id]
        self.stats["registered_components"] = len(self.component_handlers)
        
        log.debug("[InMemoryMessageBus] Unregistered component %s. Messages processed: %d", 
                  component_id, handler.message_count)
        
        return True
    
    async def _deliver_queued_messages(self, component_id: str, messages: List[MessageEnvelope]) -> None:
        """Deliver queued messages to component"""
        handler = self.component_handlers.get(component_id)
        if not handler:
            log.warning("[InMemoryMessageBus] Handler disappeared during queued delivery: %s", component_id)
            return
            
        delivered = 0
        failed = 0
        
        for envelope in messages:
            try:
                if asyncio.iscoroutinefunction(handler.handler):
                    await handler.handler(envelope)
                else:
                    handler.handler(envelope)
                
                delivered += 1
                handler.message_count += 1
                
            except Exception as e:
                log.error("[InMemoryMessageBus] Failed queued delivery to %s: %s", component_id, e)
                failed += 1
                
                # Queue for retry if eligible
                if envelope.can_retry():
                    envelope.retry_count += 1
                    self.retry_queue.append(envelope)
                else:
                    self._dead_letter(envelope, f"Queued delivery failed: {e}")
        
        self.stats["messages_delivered"] += delivered
        self.stats["messages_failed"] += failed
        self.stats["queued_messages"] = sum(len(q) for q in self.component_queues.values())
        
        log.debug("[InMemoryMessageBus] Delivered queued messages to %s: %d success, %d failed", 
                  component_id, delivered, failed)
    
    async def _retry_processor(self) -> None:
        """Background task to process retry queue"""
        log.debug("[InMemoryMessageBus] Started retry processor")
        
        while self.running:
            try:
                if not self.retry_queue:
                    await asyncio.sleep(1.0)
                    continue
                
                # Process retries with exponential backoff
                messages_to_retry = []
                current_time = time.time()
                
                for envelope in self.retry_queue[:]:  # Copy to avoid modification during iteration
                    # Calculate backoff delay: 2^retry_count seconds
                    backoff_delay = min(2 ** envelope.retry_count, 60)  # Max 60 seconds
                    
                    if current_time - envelope.created_at >= backoff_delay:
                        messages_to_retry.append(envelope)
                        self.retry_queue.remove(envelope)
                
                # Retry messages
                for envelope in messages_to_retry:
                    if envelope.pattern == MessagePattern.PUBLISH_SUBSCRIBE:
                        success = await self.publish(envelope)
                    else:
                        success = await self.send_to_component(envelope)
                    
                    if success:
                        log.debug("[InMemoryMessageBus] Retry succeeded for %s", envelope.message_id)
                    else:
                        log.debug("[InMemoryMessageBus] Retry failed for %s", envelope.message_id)
                
                await asyncio.sleep(0.5)  # Check every 500ms
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("[InMemoryMessageBus] Error in retry processor: %s", e)
                await asyncio.sleep(1.0)
        
        log.debug("[InMemoryMessageBus] Retry processor stopped")
    
    async def _cleanup_processor(self) -> None:
        """Background task to cleanup expired messages and stats"""
        log.debug("[InMemoryMessageBus] Started cleanup processor")
        
        while self.running:
            try:
                await asyncio.sleep(30.0)  # Run every 30 seconds
                
                current_time = time.time()
                cleaned_count = 0
                
                # Clean expired messages from retry queue
                self.retry_queue = [
                    envelope for envelope in self.retry_queue 
                    if not envelope.is_expired()
                ]
                
                # Clean expired messages from component queues
                for component_id, queue in self.component_queues.items():
                    original_size = len(queue)
                    expired_messages = []
                    
                    # Find expired messages
                    for envelope in list(queue):
                        if envelope.is_expired():
                            expired_messages.append(envelope)
                            queue.remove(envelope)
                    
                    # Dead letter expired messages
                    for envelope in expired_messages:
                        self._dead_letter(envelope, "Message expired")
                        cleaned_count += 1
                    
                    if expired_messages:
                        log.debug("[InMemoryMessageBus] Cleaned %d expired messages from %s queue", 
                                  len(expired_messages), component_id)
                
                # Update stats
                self.stats["queued_messages"] = sum(len(q) for q in self.component_queues.values())
                
                if cleaned_count > 0:
                    log.debug("[InMemoryMessageBus] Cleanup cycle completed: %d messages cleaned", cleaned_count)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("[InMemoryMessageBus] Error in cleanup processor: %s", e)
        
        log.debug("[InMemoryMessageBus] Cleanup processor stopped")
    
    def _dead_letter(self, envelope: MessageEnvelope, reason: str) -> None:
        """Move message to dead letter queue"""
        self.dead_letter_queue.append({
            "envelope": envelope.to_dict(),
            "reason": reason,
            "dead_lettered_at": time.time()
        })
        
        self.stats["messages_dead_lettered"] += 1
        
        log.warning("[InMemoryMessageBus] Dead lettered message %s: %s", envelope.message_id, reason)
    
    def _update_avg_delivery_time(self, delivery_time_ms: float) -> None:
        """Update rolling average delivery time"""
        current_avg = self.stats["avg_delivery_time_ms"]
        # Simple rolling average with weight
        self.stats["avg_delivery_time_ms"] = current_avg * 0.9 + delivery_time_ms * 0.1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive message bus statistics"""
        uptime = time.time() - self.start_time if self.running else 0
        
        return {
            # Basic state
            "running": self.running,
            "uptime_seconds": uptime,
            
            # Core statistics
            **self.stats,
            
            # Calculated metrics
            "messages_per_second": self.stats["messages_published"] / max(uptime, 1),
            "delivery_success_rate": (
                self.stats["messages_delivered"] / max(self.stats["messages_published"], 1)
            ),
            
            # Current state
            "active_topics": len(self.topic_subscribers),
            "retry_queue_size": len(self.retry_queue),
            "dead_letter_queue_size": len(self.dead_letter_queue),
            
            # Component handler stats
            "component_handlers": {
                comp_id: {
                    "message_count": handler.message_count,
                    "last_message_at": handler.last_message_at,
                    "registered_duration": time.time() - handler.registered_at
                }
                for comp_id, handler in self.component_handlers.items()
            }
        }
    
    def is_healthy(self) -> bool:
        """Check if message bus is healthy"""
        if not self.running:
            return False
            
        # Check for excessive failures
        if self.stats["delivery_failures"] > 100:
            log.warning("[InMemoryMessageBus] High delivery failure count: %d", 
                       self.stats["delivery_failures"])
            return False
            
        # Check for excessive dead letters
        if len(self.dead_letter_queue) > 50:
            log.warning("[InMemoryMessageBus] High dead letter count: %d", 
                       len(self.dead_letter_queue))
            return False
            
        # Check background tasks
        if self._retry_task and self._retry_task.done():
            log.warning("[InMemoryMessageBus] Retry processor task died")
            return False
            
        if self._cleanup_task and self._cleanup_task.done():
            log.warning("[InMemoryMessageBus] Cleanup processor task died")
            return False
        
        return True