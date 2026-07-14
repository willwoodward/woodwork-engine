from abc import ABC, abstractmethod

from woodwork.components.component import Component
from woodwork.utils import format_kwargs


class Memory(Component, ABC):
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
