from langchain_openai import ChatOpenAI

from woodwork.helper_functions import print_debug, get_optional, format_kwargs
from woodwork.components.llms.llm import llm


class openai(llm):
    def __init__(self, api_key: str, model="gpt-4o-mini", **config):
        format_kwargs(config, api_key=api_key, model=model, type="openai")
        print_debug("Establishing connection with model...")

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

        print_debug("Model initialised.")

    @property
    def _llm(self):
        return self._llm_value
