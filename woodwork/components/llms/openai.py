from langchain_openai import ChatOpenAI

from woodwork.helper_functions import print_debug
from woodwork.components.llms.llm import llm

class openai(llm):
    def __init__(self, name, api_key: str, model="gpt-4o", **config):
        print_debug(f"Establishing connection with model...")
        
        self._llm_value = ChatOpenAI(
            model=model,
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=api_key
        )
        
        self._retriever = config.get("knowledge_base")
        if self._retriever:
            self._retriever = self._retriever.retriever
        
        super().__init__(name, **config)

        print_debug("Model initialised.")

    @property
    def _llm(self): return self._llm_value
