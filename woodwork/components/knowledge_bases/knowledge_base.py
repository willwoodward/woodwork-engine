from abc import ABC, abstractmethod
import os
import shutil

from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.helper_functions import format_kwargs


class knowledge_base(component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="knowledge_base")
        super().__init__(**config)

    def embed_init(self):
        if self._file_to_embed is not None and os.path.exists(self._file_to_embed):
            with open(self._file_to_embed, "r") as file:
                self.embed(file.read())

    def clear_all(self):
        if os.path.exists(self._path):
            shutil.rmtree(self._path)

    @abstractmethod
    def query(self, query):
        pass

    @property
    @abstractmethod
    def retriever():
        # Each knowledge base should come with a default retriever. For use with LLMs.
        pass

    @property
    @abstractmethod
    def embedding_model(self):
        # Each knowledge base should come with a default embedding model.
        return self._embedding_model
