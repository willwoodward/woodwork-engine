from abc import ABC, abstractmethod

from woodwork.components.component import component

class api(component, ABC):
    def __init__(self, name, config):
        super().__init__(name, "api")
    
    @abstractmethod
    def call(self, req, inputs):
        pass
    
    @abstractmethod
    def describe(self):
        pass