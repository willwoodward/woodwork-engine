"""
Streaming data types for Woodwork components

This module defines the core data structures for streaming data between components,
including chunks, metadata, and stream status tracking.
"""

from typing import AsyncGenerator, Optional, Union, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid
import time
import json
import hashlib
import base64


class StreamDataType(Enum):
    """Supported data types for streaming"""
    TEXT = "text"
    AUDIO = "audio" 
    IMAGE = "image"
    BINARY = "binary"
    JSON = "json"


class StreamStatus(Enum):
    """Stream status states"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StreamChunk:
    """Individual chunk in a data stream with reliability metadata"""
    stream_id: str
    chunk_index: int
    data: Union[str, bytes, dict, Any]
    data_type: StreamDataType
    is_final: bool = False
    chunk_size: Optional[int] = None
    checksum: Optional[str] = None  # For data integrity
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Calculate chunk size and checksum if not provided"""
        if self.chunk_size is None:
            if isinstance(self.data, str):
                self.chunk_size = len(self.data.encode('utf-8'))
            elif isinstance(self.data, bytes):
                self.chunk_size = len(self.data)
            elif isinstance(self.data, dict):
                self.chunk_size = len(json.dumps(self.data).encode('utf-8'))
            else:
                self.chunk_size = len(str(self.data).encode('utf-8'))
        
        if self.checksum is None:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum of the data"""
        if isinstance(self.data, str):
            data_bytes = self.data.encode('utf-8')
        elif isinstance(self.data, bytes):
            data_bytes = self.data
        elif isinstance(self.data, dict):
            data_bytes = json.dumps(self.data, sort_keys=True).encode('utf-8')
        else:
            data_bytes = str(self.data).encode('utf-8')
        
        return hashlib.sha256(data_bytes).hexdigest()[:16]  # First 16 chars
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for message bus transport"""
        return {
            "stream_id": self.stream_id,
            "chunk_index": self.chunk_index,
            "data": self._serialize_data(),
            "data_type": self.data_type.value,
            "is_final": self.is_final,
            "chunk_size": self.chunk_size,
            "checksum": self.checksum,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
    
    def _serialize_data(self) -> Union[str, Dict[str, Any]]:
        """Serialize data based on type for JSON transport"""
        if self.data_type == StreamDataType.JSON:
            return self.data
        elif self.data_type == StreamDataType.BINARY:
            if isinstance(self.data, bytes):
                return base64.b64encode(self.data).decode('utf-8')
            else:
                return base64.b64encode(str(self.data).encode('utf-8')).decode('utf-8')
        else:
            return str(self.data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamChunk':
        """Deserialize from message bus transport"""
        chunk = cls(
            stream_id=data["stream_id"],
            chunk_index=data["chunk_index"],
            data=data["data"],  # Will be deserialized based on type
            data_type=StreamDataType(data["data_type"]),
            is_final=data.get("is_final", False),
            chunk_size=data.get("chunk_size"),
            checksum=data.get("checksum"),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", time.time())
        )
        chunk._deserialize_data(data["data"])
        return chunk
        
    def _deserialize_data(self, serialized_data: Any):
        """Deserialize data based on type"""
        if self.data_type == StreamDataType.BINARY:
            if isinstance(serialized_data, str):
                self.data = base64.b64decode(serialized_data.encode('utf-8'))
            else:
                self.data = serialized_data
        elif self.data_type == StreamDataType.JSON:
            self.data = serialized_data
        else:
            self.data = serialized_data
    
    def verify_checksum(self) -> bool:
        """Verify data integrity using checksum"""
        return self.checksum == self._calculate_checksum()


@dataclass
class StreamMetadata:
    """Metadata for stream management and monitoring"""
    stream_id: str
    session_id: str
    component_source: str
    component_target: str
    data_type: StreamDataType
    status: StreamStatus = StreamStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    total_chunks: Optional[int] = None
    bytes_transferred: int = 0
    last_chunk_at: float = field(default_factory=time.time)
    
    # Reliability tracking
    expected_chunks: int = 0
    received_chunks: int = 0
    missing_chunks: List[int] = field(default_factory=list)
    
    # Performance metrics
    avg_chunk_size: float = 0.0
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata for storage/transport"""
        return {
            "stream_id": self.stream_id,
            "session_id": self.session_id,
            "component_source": self.component_source,
            "component_target": self.component_target,
            "data_type": self.data_type.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "total_chunks": self.total_chunks,
            "bytes_transferred": self.bytes_transferred,
            "last_chunk_at": self.last_chunk_at,
            "expected_chunks": self.expected_chunks,
            "received_chunks": self.received_chunks,
            "missing_chunks": self.missing_chunks,
            "avg_chunk_size": self.avg_chunk_size,
            "processing_time": self.processing_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreamMetadata':
        """Deserialize metadata from storage/transport"""
        return cls(
            stream_id=data["stream_id"],
            session_id=data["session_id"],
            component_source=data["component_source"],
            component_target=data["component_target"],
            data_type=StreamDataType(data["data_type"]),
            status=StreamStatus(data.get("status", "active")),
            created_at=data.get("created_at", time.time()),
            completed_at=data.get("completed_at"),
            total_chunks=data.get("total_chunks"),
            bytes_transferred=data.get("bytes_transferred", 0),
            last_chunk_at=data.get("last_chunk_at", time.time()),
            expected_chunks=data.get("expected_chunks", 0),
            received_chunks=data.get("received_chunks", 0),
            missing_chunks=data.get("missing_chunks", []),
            avg_chunk_size=data.get("avg_chunk_size", 0.0),
            processing_time=data.get("processing_time", 0.0)
        )
    
    def update_stats(self, chunk: StreamChunk):
        """Update statistics from a received chunk"""
        self.received_chunks += 1
        self.bytes_transferred += chunk.chunk_size or 0
        self.last_chunk_at = time.time()
        
        # Update average chunk size
        if self.received_chunks > 1:
            self.avg_chunk_size = (
                (self.avg_chunk_size * (self.received_chunks - 1) + (chunk.chunk_size or 0))
                / self.received_chunks
            )
        else:
            self.avg_chunk_size = chunk.chunk_size or 0
        
        # Update status if final chunk
        if chunk.is_final:
            self.status = StreamStatus.COMPLETED
            self.completed_at = time.time()
            self.total_chunks = self.expected_chunks
            self.processing_time = self.completed_at - self.created_at


class StreamBuffer:
    """Buffer for ordering and managing stream chunks"""
    
    def __init__(self, stream_id: str, max_size: int = 1000):
        self.stream_id = stream_id
        self.max_size = max_size
        self.chunks: Dict[int, StreamChunk] = {}
        self.next_expected_index = 0
        self.is_complete = False
        
    def add_chunk(self, chunk: StreamChunk) -> bool:
        """Add chunk to buffer, returns True if successfully added"""
        if len(self.chunks) >= self.max_size:
            return False  # Buffer full
        
        if chunk.stream_id != self.stream_id:
            return False  # Wrong stream
        
        self.chunks[chunk.chunk_index] = chunk
        
        if chunk.is_final:
            self.is_complete = True
            
        return True
    
    def get_next_chunk(self) -> Optional[StreamChunk]:
        """Get next chunk in sequence, None if not available"""
        if self.next_expected_index in self.chunks:
            chunk = self.chunks.pop(self.next_expected_index)
            self.next_expected_index += 1
            return chunk
        return None
    
    def get_available_chunks(self) -> List[StreamChunk]:
        """Get all available chunks in order"""
        chunks = []
        while True:
            chunk = self.get_next_chunk()
            if chunk is None:
                break
            chunks.append(chunk)
        return chunks
    
    def has_missing_chunks(self) -> List[int]:
        """Return list of missing chunk indices up to current point"""
        missing = []
        for i in range(self.next_expected_index):
            if i not in self.chunks:
                missing.append(i)
        return missing
    
    def is_ready_for_completion(self) -> bool:
        """Check if stream can be completed (all chunks received)"""
        return self.is_complete and len(self.chunks) == 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        return {
            "stream_id": self.stream_id,
            "buffered_chunks": len(self.chunks),
            "next_expected": self.next_expected_index,
            "is_complete": self.is_complete,
            "missing_chunks": self.has_missing_chunks()
        }


def generate_stream_id() -> str:
    """Generate unique stream ID"""
    return f"stream-{uuid.uuid4().hex[:12]}"


def create_stream_chunk(
    stream_id: str,
    chunk_index: int,
    data: Any,
    data_type: StreamDataType = StreamDataType.TEXT,
    is_final: bool = False,
    metadata: Optional[Dict[str, Any]] = None
) -> StreamChunk:
    """Convenience function to create a stream chunk"""
    return StreamChunk(
        stream_id=stream_id,
        chunk_index=chunk_index,
        data=data,
        data_type=data_type,
        is_final=is_final,
        metadata=metadata or {}
    )