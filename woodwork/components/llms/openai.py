import logging
import multiprocessing
from langchain_openai import ChatOpenAI
import time

from woodwork.components.llms.llm import llm
from woodwork.interfaces import ParallelStartable, Startable
from woodwork.utils import format_kwargs, get_optional

log = logging.getLogger(__name__)


class openai(llm, ParallelStartable, Startable):
    def __init__(self, api_key: str, model="gpt-4o-mini", **config):
        format_kwargs(config, api_key=api_key, model=model, type="openai")
        log.debug("Establishing connection with model...")
        self._model = model
        self._api_key = api_key
        self._retriever = get_optional(config, "knowledge_base")
        if self._retriever is not None:
            self._retriever = self._retriever.retriever
        
        if self._model == "gpt-5-mini":
            self._llm_value = ChatOpenAI(
                model=self._model,
                max_tokens=None,
                timeout=None,
                max_retries=2,
                api_key=self._api_key,
            )

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
        if self._model == "gpt-5-mini":
            log.debug("Model initialized.")
            return
        self._llm_value = ChatOpenAI(
            model=self._model,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=self._api_key,
        )
        time.sleep(1)
        log.debug("Model initialized.")
