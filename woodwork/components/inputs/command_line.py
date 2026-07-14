import logging
from typing import AsyncGenerator

from woodwork.components.inputs.inputs import Input
from woodwork.utils import format_kwargs

log = logging.getLogger(__name__)


class CommandLineInput(Input):
    def __init__(self, **config):
        format_kwargs(config, type="command_line")
        super().__init__(**config)
        log.debug("Creating command line input...")
        self._last_result: str = ""

    def input_function(self) -> str:
        return input()

    # --- New stream() / respond() API used by AsyncRuntime ---

    async def stream(self) -> AsyncGenerator[str, None]:
        """Yield user queries one at a time from stdin.

        Uses asyncio's native pipe reader so that task cancellation (Ctrl+C)
        propagates immediately without leaving a blocking thread behind.
        """
        import asyncio
        import sys

        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        try:
            while True:
                try:
                    line = await reader.readline()
                except asyncio.CancelledError:
                    return
                if not line:  # EOF (Ctrl+D)
                    break
                yield line.decode().rstrip("\n")
        finally:
            transport.close()

    async def respond(self, result: str) -> None:
        """Print the agent's response to stdout."""
        print(result)

    # Legacy alias
    def input(self) -> str:
        return self.input_function()
