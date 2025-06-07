from abc import ABC, abstractmethod


class initializable(ABC):
    @abstractmethod
    def init(self, config: dict):
        pass
