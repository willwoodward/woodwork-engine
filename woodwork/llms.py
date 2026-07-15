"""Convenience re-exports for LLM components.

These thin subclasses provide a clean public API — users never need to pass
``component`` or ``type`` explicitly.

Example::

    from woodwork.llms import OpenAI, Claude, Ollama

    model = OpenAI(name="model", api_key=Env("OPENAI_API_KEY"), model="gpt-4o-mini")
"""

from woodwork.components.llms.openai import OpenAILLM
from woodwork.components.llms.claude import ClaudeLLM
from woodwork.components.llms.ollama import OllamaLLM
from woodwork.components.llms.hugging_face import HuggingFaceLLM


class OpenAI(OpenAILLM):
    """OpenAI LLM component for the woodwork Python API."""

    def __init__(self, name: str, api_key: str, model: str = "gpt-4o-mini", **kwargs):
        super().__init__(name=name, api_key=api_key, model=model, **kwargs)


class Claude(ClaudeLLM):
    """Anthropic Claude LLM component for the woodwork Python API."""

    def __init__(self, name: str, api_key: str, model: str = "claude-sonnet-4-20250514", **kwargs):
        super().__init__(name=name, api_key=api_key, model=model, **kwargs)


class Ollama(OllamaLLM):
    """Ollama LLM component for the woodwork Python API."""

    def __init__(self, name: str, model: str, **kwargs):
        super().__init__(name=name, model=model, **kwargs)


class HuggingFace(HuggingFaceLLM):
    """HuggingFace LLM component for the woodwork Python API."""

    def __init__(self, name: str, api_key: str, model: str = "mistralai/Mixtral-8x7B-Instruct-v0.1", **kwargs):
        super().__init__(name=name, api_key=api_key, model=model, **kwargs)


__all__ = ["OpenAI", "Claude", "Ollama", "HuggingFace"]
