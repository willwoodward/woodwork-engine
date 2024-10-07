from abc import ABC, abstractmethod

from woodwork.components.component import component

class knowledge_base(ABC, component):
    def __init__(self, name):
        super().__init__(name, "knowledge_base")

    @abstractmethod
    def query(self, query):
        pass
