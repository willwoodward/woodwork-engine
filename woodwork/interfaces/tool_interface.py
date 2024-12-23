from abc import ABC, abstractmethod


class tool_interface(ABC):
    @abstractmethod
    def input(self, action: str, inputs: dict):
        pass

    @property
    @abstractmethod
    def description(self):
        pass
