from abc import ABC, abstractmethod
import multiprocessing


class Initializable(ABC):
    @abstractmethod
    def init(self, queue: multiprocessing.Queue, config: dict):
        pass
