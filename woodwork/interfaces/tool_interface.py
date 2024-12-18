from abc import ABC, abstractmethod

class tool_interface(ABC):
    @abstractmethod
    def input(self, *args, **kwargs):
        pass
    
    @property
    @abstractmethod
    def description(self): pass