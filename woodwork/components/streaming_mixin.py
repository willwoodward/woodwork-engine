"""
Streaming Mixin for Woodwork Components

This mixin provides streaming capabilities to components based on their
configuration. Components can be configured for input streaming, output
streaming, both, or neither.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Any, Dict, Union, List

from woodwork.core.stream_manager import StreamManager
from woodwork.types.streaming_data import StreamDataType, StreamChunk

log = logging.getLogger(__name__)


class StreamingMixin:
    """Mixin to add streaming capabilities to components based on configuration"""
    
    def __init__(self, *args, **kwargs):
        # Only call super().__init__() if there are other base classes with __init__
        try:
            super().__init__(*args, **kwargs)
        except TypeError:
            # If no other base class needs initialization, just pass
            pass
            
        self._stream_manager: Optional[StreamManager] = None
        
        # Parse streaming configuration from component config
        config = getattr(self, 'config', kwargs.get('config', {}))
        self.streaming_enabled = config.get('streaming', False)
        
        # Let components define their own streaming capabilities
        # Default: components can stream both input and output if streaming is enabled
        self.streaming_input = self.streaming_enabled and self._can_stream_input()
        self.streaming_output = self.streaming_enabled and self._can_stream_output()
        
        # Component identification for streaming
        self.component_name = getattr(self, 'name', kwargs.get('name', 'unknown'))
        
        log.debug(f"Component {self.component_name} streaming config: "
                  f"input={self.streaming_input}, output={self.streaming_output}")
    
    def _can_stream_input(self) -> bool:
        """Override in subclasses to define input streaming capability"""
        # Default: most components can stream input
        return True
    
    def _can_stream_output(self) -> bool:
        """Override in subclasses to define output streaming capability"""
        # Default: most components can stream output
        return True
        
    def set_stream_manager(self, stream_manager: StreamManager):
        """Set the stream manager for this component"""
        self._stream_manager = stream_manager
        log.debug(f"Stream manager set for component {self.component_name}")
        
    async def create_output_stream(
        self,
        target_component: str,
        data_type: StreamDataType = StreamDataType.TEXT,
        session_id: Optional[str] = None
    ) -> str:
        """Create output stream to target component"""
        if not self._stream_manager:
            raise RuntimeError(f"StreamManager not configured for {self.component_name}")
            
        if not self.streaming_output:
            raise RuntimeError(f"Streaming output not enabled for {self.component_name}")
            
        return await self._stream_manager.create_stream(
            session_id=session_id or self._get_session_id(),
            component_source=self.component_name,
            component_target=target_component,
            data_type=data_type
        )
        
    async def stream_output(self, stream_id: str, data: Any, is_final: bool = False):
        """Send data chunk to output stream"""
        if not self._stream_manager:
            raise RuntimeError(f"StreamManager not configured for {self.component_name}")
            
        if not self.streaming_output:
            raise RuntimeError(f"Streaming output not enabled for {self.component_name}")
        
        log.debug(f"StreamingMixin sending chunk to {stream_id}: '{data}' (final={is_final})")
        success = await self._stream_manager.send_chunk(stream_id, data, is_final)
        if not success:
            log.warning(f"Failed to send chunk to stream {stream_id}")
        else:
            log.debug(f"Successfully sent chunk to stream {stream_id}")
            
        return success
        
    async def receive_input_stream(self, stream_id: str) -> AsyncGenerator[Any, None]:
        """Receive input stream chunks"""
        if not self._stream_manager:
            raise RuntimeError(f"StreamManager not configured for {self.component_name}")
            
        if not self.streaming_input:
            raise RuntimeError(f"Streaming input not enabled for {self.component_name}")
            
        async for chunk in self._stream_manager.receive_stream(stream_id):
            yield chunk.data
            
    async def process_input(self, data: Union[Any, str]) -> Any:
        """
        Process input - can handle both streaming and non-streaming data
        
        This method provides intelligent routing between streaming and non-streaming
        processing based on the input data format and component configuration.
        """
        
        # Check if this is a stream reference
        if isinstance(data, str) and data.startswith("stream:"):
            return await self._handle_streaming_input(data)
        else:
            return await self._handle_regular_input(data)
    
    async def _handle_streaming_input(self, stream_data: str) -> Any:
        """Handle streaming input data"""
        stream_id = stream_data.replace("stream:", "")
        
        if self.streaming_input:
            # Component can process streaming input
            return await self._process_streaming_input(stream_id)
        else:
            # Component needs full input - accumulate stream first
            return await self._accumulate_and_process(stream_id)
    
    async def _handle_regular_input(self, data: Any) -> Any:
        """Handle regular non-streaming input"""
        # For regular input, just call the component's process method
        if hasattr(self, 'process'):
            result = self.process(data)
            # Handle both sync and async process methods
            if asyncio.iscoroutine(result):
                return await result
            return result
        else:
            # Default processing - just return the data
            return data
    
    async def _process_streaming_input(self, stream_id: str) -> Any:
        """Process streaming input chunk by chunk (override in subclasses if needed)"""
        accumulated_data = []
        
        try:
            async for chunk in self.receive_input_stream(stream_id):
                accumulated_data.append(chunk)
                
                # Allow components to process individual chunks
                if hasattr(self, 'process_chunk'):
                    await self.process_chunk(chunk)
                    
            # Process accumulated data
            return await self._process_accumulated_input(accumulated_data)
            
        except Exception as e:
            log.error(f"Error processing streaming input for {self.component_name}: {e}")
            raise
    
    async def _accumulate_and_process(self, stream_id: str) -> Any:
        """Accumulate entire stream then process (for non-streaming components)"""
        accumulated_data = []
        
        try:
            async for chunk in self.receive_input_stream(stream_id):
                accumulated_data.append(chunk)
                
            # Combine all chunks into single input
            combined_input = self._combine_chunks(accumulated_data)
            
            # Process the combined input using regular process method
            if hasattr(self, 'process'):
                return await self.process(combined_input)
            else:
                return combined_input
                
        except Exception as e:
            log.error(f"Error accumulating stream for {self.component_name}: {e}")
            raise
    
    async def _process_accumulated_input(self, chunks: List[Any]) -> Any:
        """
        Process accumulated streaming input - override in subclasses
        
        Default implementation combines chunks and processes them as a single input.
        """
        combined_input = self._combine_chunks(chunks)
        
        if hasattr(self, 'process'):
            return await self.process(combined_input)
        else:
            return combined_input
    
    def _combine_chunks(self, chunks: List[Any]) -> str:
        """Combine chunks into single input (default: string concatenation)"""
        return "".join(str(chunk) for chunk in chunks)
    
    async def process_with_streaming_output(self, input_data: Any, target_component: str = "output") -> Union[str, Any]:
        """
        Process input and handle streaming output if enabled
        
        This is a convenience method that automatically handles streaming output
        when the component is configured for it.
        """
        
        if self.streaming_output:
            # Create output stream and process with streaming
            stream_id = await self.create_output_stream(
                target_component=target_component,
                data_type=StreamDataType.TEXT  # Default to text, override if needed
            )
            
            # Start streaming generation in background - don't await it!
            # This allows the consumer to start receiving chunks immediately
            # Add a small delay to ensure event loop is stable
            async def _delayed_generation():
                await asyncio.sleep(0.01)  # Small delay to let event loop stabilize
                await self._generate_and_stream_output(input_data, stream_id)
            
            task = asyncio.create_task(_delayed_generation())
            # Set task name for debugging
            task.set_name(f"stream_generation_{stream_id}")
            
            # Immediately return stream reference so consumer can start receiving
            # while generation happens in background
            return f"stream:{stream_id}"
        else:
            # Regular processing
            if hasattr(self, 'process'):
                result = self.process(input_data)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            else:
                return input_data
    
    async def _process_with_stream_output(self, input_data: Any, target_component: str) -> str:
        """Process input and stream the output"""
        # Create output stream
        stream_id = await self.create_output_stream(
            target_component=target_component,
            data_type=StreamDataType.TEXT  # Default to text, override if needed
        )
        
        # Process and stream output
        await self._generate_and_stream_output(input_data, stream_id)
        
        # Return stream reference
        return f"stream:{stream_id}"
    
    async def _generate_and_stream_output(self, input_data: Any, stream_id: str):
        """
        Generate and stream output data - override in subclasses
        
        Default implementation processes input and sends as single chunk.
        """
        try:
            # Process the input
            if hasattr(self, 'process'):
                result = await self.process(input_data)
            else:
                result = str(input_data)
            
            # Send as single chunk (non-streaming components)
            await self.stream_output(stream_id, result, is_final=True)
            
        except Exception as e:
            log.error(f"Error generating streaming output for {self.component_name}: {e}")
            # Send error and close stream
            await self.stream_output(stream_id, f"Error: {e}", is_final=True)
    
    def _get_session_id(self) -> str:
        """Get current session ID - override in component implementation"""
        # Try to get session ID from various sources
        if hasattr(self, 'session_id'):
            return self.session_id
        if hasattr(self, 'config') and 'session_id' in self.config:
            return self.config['session_id']
        return "default-session"
    
    def is_streaming_capable(self) -> Dict[str, bool]:
        """Return streaming capabilities of this component"""
        return {
            "streaming_input": self.streaming_input,
            "streaming_output": self.streaming_output,
            "streaming_enabled": self.streaming_enabled
        }
    
    def get_streaming_stats(self) -> Dict[str, Any]:
        """Get streaming-related statistics"""
        stats = {
            "component_name": self.component_name,
            "streaming_capabilities": self.is_streaming_capable(),
            "stream_manager_available": self._stream_manager is not None
        }
        
        if self._stream_manager:
            stats["stream_manager_stats"] = self._stream_manager.get_stats()
            
        return stats


class StreamingLLMComponent(StreamingMixin):
    """
    Example LLM component with streaming output capability
    
    This shows how to implement a component that needs full input before
    it can start streaming output (typical LLM pattern).
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name=name, config=config)
        # LLM typically needs full input before it can start streaming output
        # So it's usually streaming_input=False, streaming_output=True
        
    async def process(self, input_text: str) -> Union[str, str]:
        """Process input and return result (streaming or non-streaming)"""
        if self.streaming_output:
            return await self.process_with_streaming_output(input_text)
        else:
            # Non-streaming response
            return await self._generate_full_response(input_text)
    
    async def _generate_and_stream_output(self, input_data: Any, stream_id: str):
        """Generate streaming response token by token"""
        try:
            # Generate response tokens (this would call actual LLM API)
            tokens = await self._generate_response_tokens(str(input_data))
            
            # Stream each token
            for i, token in enumerate(tokens):
                is_final = (i == len(tokens) - 1)
                await self.stream_output(stream_id, token, is_final=is_final)
                
                # Small delay to simulate realistic streaming
                await asyncio.sleep(0.01)
                
        except Exception as e:
            log.error(f"Error in streaming LLM output: {e}")
            await self.stream_output(stream_id, f"\nError: {e}", is_final=True)
    
    async def _generate_response_tokens(self, input_text: str) -> List[str]:
        """Generate response tokens - override with actual LLM implementation"""
        # Placeholder implementation
        response = f"You said: '{input_text}'. This is a demo streaming response."
        
        # Split into tokens (simple word-based tokenization)
        tokens = []
        words = response.split()
        for word in words:
            tokens.append(word + " ")
            
        return tokens
    
    async def _generate_full_response(self, input_text: str) -> str:
        """Generate complete response at once (non-streaming)"""
        tokens = await self._generate_response_tokens(input_text)
        return "".join(tokens).strip()


class StreamingTextProcessor(StreamingMixin):
    """
    Example component that can handle both streaming input and output
    
    This might be used for text processing that can work on chunks
    as they arrive (e.g., translation, text-to-speech).
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name=name, config=config)
        
    async def process_chunk(self, chunk: Any):
        """Process individual chunk (called for streaming input)"""
        # Example: could process and immediately output each chunk
        processed = self._process_text_chunk(str(chunk))
        log.debug(f"Processed chunk: {chunk} -> {processed}")
        
    def _process_text_chunk(self, text: str) -> str:
        """Process individual text chunk - override in subclasses"""
        # Example processing: uppercase transformation
        return text.upper()
    
    async def _generate_and_stream_output(self, input_data: Any, stream_id: str):
        """Process and stream output chunk by chunk"""
        text = str(input_data)
        
        # Process in chunks (e.g., word by word)
        words = text.split()
        for i, word in enumerate(words):
            processed_word = self._process_text_chunk(word) + " "
            is_final = (i == len(words) - 1)
            
            await self.stream_output(stream_id, processed_word, is_final=is_final)
            await asyncio.sleep(0.02)  # Small delay for demonstration