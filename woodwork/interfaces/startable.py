from abc import ABC, abstractmethod


class Startable(ABC):
    @abstractmethod
    def start(self, config: dict):
        pass
