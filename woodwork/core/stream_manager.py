"""
Stream Manager for handling streaming data between components

This module provides the StreamManager class which coordinates streaming data
flow between components, manages stream state, and handles reliability concerns
like chunk ordering and missing data detection.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, AsyncGenerator, Callable, Set, Any

from woodwork.types.streaming_data import (
    StreamChunk, StreamMetadata, StreamBuffer, StreamDataType, StreamStatus,
    generate_stream_id, create_stream_chunk
)
from woodwork.core.simple_message_bus import SimpleMessageBus, MessageBusAdapter

log = logging.getLogger(__name__)


class StreamManager:
    """Manages streaming data between components with reliability guarantees"""
    
    def __init__(self, message_bus: SimpleMessageBus, state_store=None):
        self.message_bus = message_bus
        self.state_store = state_store  # For future persistent state
        
        # In-memory stream management
        self.active_streams: Dict[str, StreamMetadata] = {}
        self.stream_buffers: Dict[str, StreamBuffer] = {}
        self.stream_listeners: Dict[str, Set[asyncio.Event]] = {}
        self.completion_events: Dict[str, asyncio.Event] = {}
        
        # Backpressure management
        self.max_buffer_size = 1000  # chunks per stream
        self.max_memory_usage = 100 * 1024 * 1024  # 100MB total
        self.current_memory_usage = 0
        
        # Cleanup and monitoring
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Performance metrics
        self.stats = {
            "streams_created": 0,
            "chunks_sent": 0,
            "chunks_received": 0,
            "streams_completed": 0,
            "streams_failed": 0,
            "cleanup_runs": 0
        }
        
        # Setup message bus integration
        self._setup_message_handlers()
        
    def _setup_message_handlers(self):
        """Setup message bus handlers for streaming events"""
        # Handle incoming stream chunks
        self.message_bus.subscribe("stream.chunk", self._handle_chunk_message)
        
        # Handle stream lifecycle events
        self.message_bus.subscribe("stream.created", self._handle_stream_created)
        self.message_bus.subscribe("stream.completed", self._handle_stream_completed)
        self.message_bus.subscribe("stream.failed", self._handle_stream_failed)
    
    async def start(self):
        """Start the stream manager"""
        if self._running:
            return
            
        self._running = True
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
        log.info("Stream manager started")
        
    async def stop(self):
        """Stop the stream manager and cleanup resources"""
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup all active streams
        stream_ids = list(self.active_streams.keys())
        for stream_id in stream_ids:
            await self._cleanup_stream(stream_id)
        
        log.info("Stream manager stopped")
        
    async def create_stream(
        self,
        session_id: str,
        component_source: str, 
        component_target: str,
        data_type: StreamDataType = StreamDataType.TEXT,
        stream_id: Optional[str] = None
    ) -> str:
        """
        Create new stream and return stream_id
        
        Args:
            session_id: Session identifier
            component_source: Source component name
            component_target: Target component name
            data_type: Type of data being streamed
            stream_id: Optional custom stream ID
            
        Returns:
            Stream ID string
        """
        
        if stream_id is None:
            stream_id = generate_stream_id()
            
        # Create stream metadata
        metadata = StreamMetadata(
            stream_id=stream_id,
            session_id=session_id,
            component_source=component_source,
            component_target=component_target,
            data_type=data_type
        )
        
        # Initialize stream management structures
        self.active_streams[stream_id] = metadata
        self.stream_buffers[stream_id] = StreamBuffer(stream_id, self.max_buffer_size)
        self.stream_listeners[stream_id] = set()
        self.completion_events[stream_id] = asyncio.Event()
        
        # Update statistics
        self.stats["streams_created"] += 1
        
        log.debug(f"Created stream {stream_id}: {component_source} -> {component_target}")
        
        # Notify about stream creation
        await self.message_bus.publish("stream.created", {
            "stream_id": stream_id,
            "metadata": metadata.to_dict()
        })
        
        return stream_id
        
    async def send_chunk(
        self,
        stream_id: str,
        data: Any,
        is_final: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send stream chunk to target component
        
        Args:
            stream_id: Target stream ID
            data: Chunk data to send
            is_final: Whether this is the final chunk
            metadata: Optional chunk metadata
            
        Returns:
            True if chunk was sent successfully
        """
        
        if stream_id not in self.active_streams:
            log.error(f"Stream {stream_id} not found")
            return False
            
        stream_meta = self.active_streams[stream_id]
        
        if stream_meta.status != StreamStatus.ACTIVE:
            log.warning(f"Stream {stream_id} is not active (status: {stream_meta.status})")
            return False
        
        # Check backpressure
        if not await self._check_backpressure(stream_id):
            log.warning(f"Backpressure limit reached for stream {stream_id}")
            return False
        
        # Create chunk
        chunk = create_stream_chunk(
            stream_id=stream_id,
            chunk_index=stream_meta.expected_chunks,
            data=data,
            data_type=stream_meta.data_type,
            is_final=is_final,
            metadata=metadata
        )
        
        # Update stream metadata
        stream_meta.expected_chunks += 1
        stream_meta.bytes_transferred += chunk.chunk_size or 0
        stream_meta.last_chunk_at = time.time()
        
        if is_final:
            stream_meta.status = StreamStatus.COMPLETED
            stream_meta.completed_at = time.time()
            stream_meta.total_chunks = stream_meta.expected_chunks
            
        # Send via message bus
        await self.message_bus.publish("stream.chunk", {
            "chunk": chunk.to_dict(),
            "target_component": stream_meta.component_target
        })
        
        # Update memory usage tracking
        self.current_memory_usage += chunk.chunk_size or 0
        
        # Update statistics
        self.stats["chunks_sent"] += 1
        
        log.debug(f"Sent chunk {chunk.chunk_index} for stream {stream_id} (final: {is_final})")
        
        # Mark completion if final chunk
        if is_final:
            await self._complete_stream(stream_id)
            
        return True
            
    async def receive_stream(self, stream_id: str) -> AsyncGenerator[StreamChunk, None]:
        """
        Receive stream chunks as ordered async generator
        
        Args:
            stream_id: Stream ID to receive from
            
        Yields:
            StreamChunk objects in order
        """
        
        if stream_id not in self.active_streams:
            log.error(f"Stream {stream_id} not found")
            return
            
        buffer = self.stream_buffers[stream_id]
        completion_event = self.completion_events[stream_id]
        
        log.debug(f"Starting to receive stream {stream_id}")
        
        while True:
            # Get next available chunk
            chunk = buffer.get_next_chunk()
            if chunk:
                log.debug(f"Yielding chunk {chunk.chunk_index} from stream {stream_id}")
                yield chunk
                
                # Update memory usage
                self.current_memory_usage -= chunk.chunk_size or 0
                
                # Check if this was the final chunk
                if chunk.is_final:
                    log.debug(f"Stream {stream_id} completed")
                    break
            else:
                # No chunk available, wait for more data or completion
                if buffer.is_ready_for_completion():
                    log.debug(f"Stream {stream_id} completed (no more chunks)")
                    break
                    
                # Wait for new chunks or stream completion
                try:
                    await asyncio.wait_for(completion_event.wait(), timeout=30.0)
                    completion_event.clear()  # Reset for next wait
                except asyncio.TimeoutError:
                    log.warning(f"Timeout waiting for chunks in stream {stream_id}")
                    break
                    
        # Emit completion event
        await self.message_bus.publish("stream.received_complete", {
            "stream_id": stream_id,
            "chunks_received": buffer.next_expected_index
        })
        
    async def _handle_chunk_message(self, message: Dict[str, Any]):
        """Handle incoming chunk from message bus"""
        try:
            message_data = message.get("data", {})
            chunk_data = message_data.get("chunk", {})
            
            chunk = StreamChunk.from_dict(chunk_data)
            stream_id = chunk.stream_id
            
            if stream_id not in self.active_streams:
                log.warning(f"Received chunk for unknown stream {stream_id}")
                return
                
            # Add to buffer
            buffer = self.stream_buffers[stream_id]
            if buffer.add_chunk(chunk):
                # Update statistics
                self.stats["chunks_received"] += 1
                
                # Update stream metadata
                stream_meta = self.active_streams[stream_id]
                stream_meta.update_stats(chunk)
                
                # Notify waiting receivers
                completion_event = self.completion_events[stream_id]
                completion_event.set()
                
                log.debug(f"Buffered chunk {chunk.chunk_index} for stream {stream_id}")
                
                # If this was the final chunk, handle completion
                if chunk.is_final:
                    await self._complete_stream(stream_id)
                    
            else:
                log.error(f"Failed to buffer chunk for stream {stream_id}")
                
        except Exception as e:
            log.error(f"Error handling chunk message: {e}")
            
    async def _handle_stream_created(self, message: Dict[str, Any]):
        """Handle stream creation notification"""
        try:
            message_data = message.get("data", {})
            stream_id = message_data.get("stream_id")
            log.debug(f"Stream created notification: {stream_id}")
        except Exception as e:
            log.error(f"Error handling stream created message: {e}")
            
    async def _handle_stream_completed(self, message: Dict[str, Any]):
        """Handle stream completion notification"""
        try:
            message_data = message.get("data", {})
            stream_id = message_data.get("stream_id")
            
            if stream_id in self.active_streams:
                await self._complete_stream(stream_id)
                
        except Exception as e:
            log.error(f"Error handling stream completed message: {e}")
            
    async def _handle_stream_failed(self, message: Dict[str, Any]):
        """Handle stream failure notification"""
        try:
            message_data = message.get("data", {})
            stream_id = message_data.get("stream_id")
            
            if stream_id in self.active_streams:
                await self._fail_stream(stream_id, "Remote failure notification")
                
        except Exception as e:
            log.error(f"Error handling stream failed message: {e}")
            
    async def _complete_stream(self, stream_id: str):
        """Mark stream as completed and handle cleanup"""
        if stream_id not in self.active_streams:
            return
            
        stream_meta = self.active_streams[stream_id]
        if stream_meta.status == StreamStatus.COMPLETED:
            return  # Already completed
            
        stream_meta.status = StreamStatus.COMPLETED
        stream_meta.completed_at = time.time()
        
        # Notify completion
        completion_event = self.completion_events[stream_id]
        completion_event.set()
        
        # Update statistics
        self.stats["streams_completed"] += 1
        
        log.debug(f"Stream {stream_id} completed")
        
        # Schedule cleanup (don't emit event to avoid recursion)
        asyncio.create_task(self._cleanup_stream_delayed(stream_id, delay=5))
        
    async def _fail_stream(self, stream_id: str, reason: str):
        """Mark stream as failed"""
        if stream_id not in self.active_streams:
            return
            
        stream_meta = self.active_streams[stream_id]
        stream_meta.status = StreamStatus.FAILED
        
        # Update statistics
        self.stats["streams_failed"] += 1
        
        # Emit failure event
        await self.message_bus.publish("stream.failed", {
            "stream_id": stream_id,
            "reason": reason,
            "metadata": stream_meta.to_dict()
        })
        
        log.warning(f"Stream {stream_id} failed: {reason}")
        
        # Schedule cleanup
        asyncio.create_task(self._cleanup_stream_delayed(stream_id, delay=5))
        
    async def _check_backpressure(self, stream_id: str) -> bool:
        """Check if backpressure limits are exceeded"""
        
        # Check buffer size limit
        buffer = self.stream_buffers.get(stream_id)
        if buffer and len(buffer.chunks) >= self.max_buffer_size:
            return False
            
        # Check memory usage limit  
        if self.current_memory_usage >= self.max_memory_usage:
            return False
            
        return True
        
    async def _cleanup_stream_delayed(self, stream_id: str, delay: float):
        """Cleanup stream after delay"""
        await asyncio.sleep(delay)
        await self._cleanup_stream(stream_id)
        
    async def _cleanup_stream(self, stream_id: str):
        """Clean up stream resources"""
        
        # Remove from active tracking
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
            
        # Clean up buffer and update memory usage
        if stream_id in self.stream_buffers:
            buffer = self.stream_buffers[stream_id]
            for chunk in buffer.chunks.values():
                self.current_memory_usage -= chunk.chunk_size or 0
            del self.stream_buffers[stream_id]
            
        # Clean up listeners and events
        if stream_id in self.stream_listeners:
            del self.stream_listeners[stream_id]
            
        if stream_id in self.completion_events:
            del self.completion_events[stream_id]
            
        log.debug(f"Cleaned up stream {stream_id}")
        
    async def _periodic_cleanup(self):
        """Periodic cleanup of old/stale streams"""
        
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                current_time = time.time()
                stale_streams = []
                
                # Find stale streams (no activity for 5 minutes)
                for stream_id, metadata in self.active_streams.items():
                    if current_time - metadata.last_chunk_at > 300:
                        stale_streams.append(stream_id)
                        
                # Cleanup stale streams
                for stream_id in stale_streams:
                    log.warning(f"Cleaning up stale stream {stream_id}")
                    await self._fail_stream(stream_id, "Stream timeout")
                    
                if stale_streams:
                    self.stats["cleanup_runs"] += 1
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in periodic cleanup: {e}")
                
    def get_stream_info(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get current stream information"""
        if stream_id not in self.active_streams:
            return None
            
        metadata = self.active_streams[stream_id]
        buffer = self.stream_buffers[stream_id]
        
        return {
            "metadata": metadata.to_dict(),
            "buffer_stats": buffer.get_stats(),
            "listeners": len(self.stream_listeners.get(stream_id, set()))
        }
        
    def get_stats(self) -> Dict[str, Any]:
        """Get stream manager statistics"""
        return {
            **self.stats,
            "active_streams": len(self.active_streams),
            "memory_usage_bytes": self.current_memory_usage,
            "running": self._running
        }
        
    def list_active_streams(self) -> List[str]:
        """Get list of active stream IDs"""
        return list(self.active_streams.keys())


# Integration function for setting up streaming with message bus
async def setup_streaming(message_bus: SimpleMessageBus, stream_manager: Optional[StreamManager] = None):
    """Setup streaming integration with message bus"""
    
    if stream_manager is None:
        stream_manager = StreamManager(message_bus)
        
    await stream_manager.start()
    
    return stream_manager