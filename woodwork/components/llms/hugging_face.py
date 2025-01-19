from langchain_community.llms import HuggingFaceEndpoint

from woodwork.helper_functions import print_debug, format_kwargs
from woodwork.components.llms.llm import llm


class hugging_face(llm):
    def __init__(self, api_key: str, model="mistralai/Mixtral-8x7B-Instruct-v0.1", **config):
        format_kwargs(config, api_key=api_key, model=model, type="hugging_face")
        super().__init__(**config)
        print_debug("Establishing connection with model...")

        self._llm_value = HuggingFaceEndpoint(
            repo_id=model,
            temperature=0.1,
            model_kwargs={"max_length": 100},
            huggingfacehub_api_token=api_key,
        )

        self._retriever = config.get("knowledge_base")
        if self._retriever:
            self._retriever = self._retriever.retriever

        print_debug("Model initialised.")

    @property
    def _llm(self):
        return self._llm_value

    @property
    def retriever(self):
        return self._retriever
