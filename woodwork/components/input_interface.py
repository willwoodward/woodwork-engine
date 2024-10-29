from abc import ABC, abstractmethod

class input_interface(ABC):
    @abstractmethod
    def input(self, input):
        pass