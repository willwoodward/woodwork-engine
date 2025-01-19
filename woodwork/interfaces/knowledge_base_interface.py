from abc import ABC, abstractmethod


class knowledge_base_interface(ABC):
    @property
    @abstractmethod
    def retriever(self):
        pass
