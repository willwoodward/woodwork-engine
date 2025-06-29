from abc import ABC, abstractmethod
import multiprocessing


class Startable(ABC):
    @abstractmethod
    def start(self, queue: multiprocessing.Queue, config: dict):
        pass
