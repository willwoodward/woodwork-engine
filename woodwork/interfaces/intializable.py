from abc import ABC, abstractmethod
import multiprocessing


class ParallelInitializable(ABC):
    @abstractmethod
    def parallel_init(self, queue: multiprocessing.Queue, config: dict):
        """Initialize the component in a separate process."""
        pass


class Initializable(ABC):
    @abstractmethod
    def init(self, queue: multiprocessing.Queue, config: dict):
        pass
