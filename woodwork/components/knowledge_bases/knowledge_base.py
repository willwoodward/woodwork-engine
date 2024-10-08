from abc import ABC, abstractmethod

from woodwork.components.component import component

class knowledge_base(component, ABC):
    def __init__(self, name, config):
        super().__init__(name, "knowledge_base")

    @abstractmethod
    def query(self, query):
        pass
