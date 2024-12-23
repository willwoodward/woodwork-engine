from abc import ABC, abstractmethod

from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface


class knowledge_base(component, tool_interface, ABC):
    def __init__(self, name, config):
        super().__init__(name, "knowledge_base")

    @abstractmethod
    def query(self, query):
        pass
