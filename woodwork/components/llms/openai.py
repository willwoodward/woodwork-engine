import logging

from langchain_openai import ChatOpenAI

from woodwork.components.llms.llm import llm
from woodwork.helper_functions import format_kwargs, get_optional

log = logging.getLogger(__name__)


class openai(llm):
    def __init__(self, api_key: str, model="gpt-4o-mini", **config):
        format_kwargs(config, api_key=api_key, model=model, type="openai")
        log.debug("Establishing connection with model...")

        self._llm_value = ChatOpenAI(
            model=model,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=api_key,
        )

        self._retriever = get_optional(config, "knowledge_base")
        if self._retriever is not None:
            self._retriever = self._retriever.retriever

        super().__init__(**config)

        log.debug("Model initialized.")

    @property
    def _llm(self):
        return self._llm_value

    @property
    def retriever(self):
        return self._retriever
