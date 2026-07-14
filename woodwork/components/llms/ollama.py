import logging
import subprocess
import shutil

from langchain_ollama import ChatOllama

from woodwork.components.llms.llm import LLM
from woodwork.utils.errors.errors import RuntimeError
from woodwork.utils import format_kwargs, get_optional

log = logging.getLogger(__name__)


class OllamaLLM(LLM):
    def __init__(self, model, **config):
        format_kwargs(config, model=model, type="ollama")
        self._model = model
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
        """Check Ollama is installed and pull the model."""
        if not self._is_ollama_installed():
            raise RuntimeError("Ollama is not installed. Please install it from https://ollama.com.")
        self._pull_ollama_model(self._model)

    # init() alias kept for any old code that calls it directly
    def init(self) -> None:
        self.initialize()

    def start(self, queue=None, config=None) -> None:
        """Connect to the Ollama backend."""
        log.debug("Establishing connection with Ollama model...")
        self._llm_value = ChatOllama(model=self._model)
        log.debug("Ollama model initialized.")

    def _is_ollama_installed(self) -> bool:
        return shutil.which("ollama") is not None

    def _pull_ollama_model(self, model: str) -> None:
        try:
            log.debug("Pulling model: %s", model)
            subprocess.run(["ollama", "pull", model], check=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Failed to pull Ollama model: {exc}") from exc
