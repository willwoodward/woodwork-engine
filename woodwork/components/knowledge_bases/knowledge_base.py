from abc import ABC, abstractmethod
import os

from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.helper_functions import get_optional
from woodwork.globals import global_config


class knowledge_base(component, tool_interface, ABC):
    def __init__(self, name, **config):
        super().__init__(name, "knowledge_base")
    
    def embed_init(self):
        if self._file_to_embed is not None and os.path.exists(self._file_to_embed):
            with open(self._file_to_embed, "r") as file:
                self.embed(file.read())

    @abstractmethod
    def query(self, query):
        pass
