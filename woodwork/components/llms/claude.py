import logging
import multiprocessing
import time

# NOTE: import langchain_anthropic.ChatAnthropic lazily inside start()
# to avoid import-time errors when the optional dependency isn't installed.

from woodwork.components.llms.llm import llm
from woodwork.interfaces import ParallelStartable, Startable
from woodwork.utils import format_kwargs, get_optional

log = logging.getLogger(__name__)


class claude(llm, ParallelStartable, Startable):
    def __init__(self, api_key: str, model="claude-sonnet-4-20250514", **config):
        format_kwargs(config, api_key=api_key, model=model, type="claude")
        log.debug("Establishing connection with Claude model...")
        self._model = model
        self._api_key = api_key
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

    def parallel_start(self, queue: multiprocessing.Queue, config: dict = {}):
        time.sleep(1)

    def start(self, queue: multiprocessing.Queue, config: dict = {}):
        # Import ChatAnthropic here so tests can import this module even when
        # the optional langchain_anthropic package is not installed. Tests
        # can monkeypatch claude.ChatAnthropic before calling start().
        try:
            from langchain_anthropic import ChatAnthropic
        except Exception:
            # If import fails, leave ChatAnthropic undefined so callers/tests
            # can monkeypatch claude.ChatAnthropic as needed.
            ChatAnthropic = None

        if ChatAnthropic is None:
            # Defer raising until someone actually tries to start without a
            # patched ChatAnthropic; create a clear error message.
            raise RuntimeError(
                "ChatAnthropic (langchain_anthropic) is not installed. "
                "Install the optional dependency or monkeypatch claude.ChatAnthropic in tests."
            )

        self._llm_value = ChatAnthropic(
            model=self._model,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=self._api_key,
        )
        time.sleep(1)
        log.debug("Claude model initialized.")
