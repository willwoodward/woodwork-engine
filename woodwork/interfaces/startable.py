from abc import ABC, abstractmethod
import multiprocessing


class ParallelStartable(ABC):
    @abstractmethod
    def parallel_start(self, queue: multiprocessing.Queue, config: dict):
        """Start the component in a separate process."""
        pass

class Startable(ABC):
    @abstractmethod
    def start(self, queue: multiprocessing.Queue, config: dict):
        pass
