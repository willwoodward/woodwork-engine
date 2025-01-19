from abc import ABC, abstractmethod

from woodwork.components.component import component
from woodwork.helper_functions import format_kwargs


class memory(component, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="memory")
        super().__init__(**config)

    @property
    @abstractmethod
    def data(self):
        pass

    @abstractmethod
    def add(self, text: str):
        pass

    @abstractmethod
    def clear(self):
        pass
