import logging
from typing import Any

from woodwork.components.outputs.outputs import outputs
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class console(outputs):
    """Console output component with streaming support"""
    
    def __init__(self, **config):
        format_kwargs(config, type="console")
        super().__init__(**config)
        log.debug("Creating console output component...")
    
    def input(self, data: Any):
        """Output data to console (non-streaming)"""
        print(data)
    
    async def process_input(self, data: Any):
        """Handle both streaming and non-streaming input"""
        if isinstance(data, str) and data.startswith("stream:"):
            await self._handle_streaming_input(data)
        else:
            self.input(data)
    
    async def _handle_streaming_input(self, stream_data: str):
        """Handle streaming input - display chunks as they arrive"""
        stream_id = stream_data.replace("stream:", "")
        
        try:
            if self._stream_manager:
                async for chunk in self._stream_manager.receive_stream(stream_id):
                    print(chunk.data, end="", flush=True)
                print()  # New line at the end
            else:
                # Fallback if no stream manager
                print(f"Stream output: {stream_id}")
        except Exception as e:
            log.error(f"Error handling streaming input: {e}")
            print(f"Error displaying stream: {e}")