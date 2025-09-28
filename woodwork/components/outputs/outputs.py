from abc import abstractmethod
import asyncio
from typing import Any

from woodwork.components.component import component
from woodwork.utils import format_kwargs


class outputs(component):
    def __init__(self, **config):
        format_kwargs(config, component="output")
        super().__init__(**config)
    
    def _can_stream_input(self) -> bool:
        """Output components can typically receive streaming input"""
        return True
    
    def _can_stream_output(self) -> bool:
        """Output components typically don't stream further output"""
        return False

    @abstractmethod
    def input(self, data):
        return
    
    async def async_input(self, data: Any):
        """Async version of input that handles streaming"""
        if isinstance(data, str) and data.startswith("stream:"):
            await self._handle_streaming_input(data)
        else:
            # Handle both sync and async input methods
            result = self.input(data)
            if asyncio.iscoroutine(result):
                await result
            return result
    
    async def _handle_streaming_input(self, stream_data: str):
        """Handle streaming input - override in subclasses if needed"""
        if hasattr(self, 'process_input'):
            # If component has streaming support, use it
            await self.process_input(stream_data)
        else:
            # Fallback: accumulate stream and call regular input method
            stream_id = stream_data.replace("stream:", "")
            accumulated_data = []
            
            if self._stream_manager:
                async for chunk in self._stream_manager.receive_stream(stream_id):
                    accumulated_data.append(chunk.data)
                
                combined_data = "".join(str(chunk) for chunk in accumulated_data)
                self.input(combined_data)
