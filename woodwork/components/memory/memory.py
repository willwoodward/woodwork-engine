from abc import ABC, abstractmethod

from woodwork.components.component import component

class memory(component, ABC):
    def __init__(self, name, config):
        super().__init__(name, "memory")
    
    @abstractmethod
    @property
    def data(self):
        pass
    
    @abstractmethod
    def add(self, text: str):
        pass
    
    @abstractmethod
    def clear(self):
        pass
