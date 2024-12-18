from abc import ABC, abstractmethod

from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface

class memory(component, tool_interface, ABC):
    def __init__(self, name, config):
        super().__init__(name, "memory")

    @property
    @abstractmethod
    def data(self):
        pass
    
    @abstractmethod
    def add(self, text: str):
        pass
    
    @abstractmethod
    def clear(self):
        pass
