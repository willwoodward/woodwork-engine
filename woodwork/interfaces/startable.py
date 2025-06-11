from abc import ABC, abstractmethod


class Startable(ABC):
    @abstractmethod
    def init(self, config: dict):
        pass
