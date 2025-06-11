import logging
from langchain_ollama import OllamaLLM as Ollama
import subprocess
import shutil

from woodwork.components.llms.llm import llm
from woodwork.errors import RuntimeError
from woodwork.helper_functions import format_kwargs, get_optional
from woodwork.interfaces import Initializable, Startable

log = logging.getLogger(__name__)


class ollama(llm, Initializable, Startable):
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

    def init(self) -> None:
        """Initialize the Ollama model."""
        if not self._is_ollama_installed():
            raise RuntimeError("Ollama is not installed. Please install it from https://ollama.com.")

        # Pulling the model, does not redownload if already present
        self._pull_ollama_model(self._model)

    def start(self) -> None:
        """Start the Ollama model."""
        log.debug("Establishing connection with model...")
        self._llm_value = Ollama(
            model=self._model,
        )
        log.debug("Model initialized.")

    def _is_ollama_installed(self) -> bool:
        return shutil.which("ollama") is not None

    def _pull_ollama_model(self, model: str) -> None:
        """Pull the model using `ollama pull`."""
        try:
            log.debug(f"Pulling model: {model}")
            subprocess.run(["ollama", "pull", model], check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to pull Ollama model: {e}")
