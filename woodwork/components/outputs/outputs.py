from abc import abstractmethod

from woodwork.components.component import component
from woodwork.utils import format_kwargs


class outputs(component):
    def __init__(self, **config):
        format_kwargs(config, component="output")
        super().__init__(**config)

    @abstractmethod
    def input(self, data):
        return
