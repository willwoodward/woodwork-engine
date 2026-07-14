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
        """Yield user queries one at a time from stdin."""
        import asyncio
        loop = asyncio.get_event_loop()
        while True:
            query = await loop.run_in_executor(None, self.input_function)
            yield query

    async def respond(self, result: str) -> None:
        """Print the agent's response to stdout."""
        print(result)

    # Legacy alias
    def input(self) -> str:
        return self.input_function()
