import logging
import time

from langchain_anthropic import ChatAnthropic

from woodwork.components.llms.llm import LLM
from woodwork.utils import format_kwargs, get_optional

log = logging.getLogger(__name__)


class ClaudeLLM(LLM):
    def __init__(self, api_key: str, model="claude-sonnet-4-20250514", **config):
        format_kwargs(config, api_key=api_key, model=model, type="claude")
        log.debug("Establishing connection with Claude model...")
        self._model = model
        self._api_key = api_key
        self._llm_value = None
        self._retriever = get_optional(config, "knowledge_base")
        if self._retriever is not None:
            self._retriever = self._retriever.retriever
        super().__init__(**config)

    @property
    def _llm(self):
        return self._llm_value

    @property
    def retriever(self):
        return self._retriever

    def initialize(self) -> None:
        """Initialise the Anthropic client."""
        self._llm_value = ChatAnthropic(
            model=self._model,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=self._api_key,
        )
        log.debug("Claude model initialized.")

    # Legacy start() for old runtime paths
    def start(self, queue=None, config=None):
        self.initialize()
        time.sleep(1)

    def parallel_start(self, queue=None, config=None):
        time.sleep(1)
