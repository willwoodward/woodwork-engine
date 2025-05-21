from abc import ABC, abstractmethod

from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.helper_functions import format_kwargs


class model(component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="model")
        super().__init__(**config)

    @property
    @abstractmethod
    def input_dim(self):
        """The input dimension of the model."""
        pass

    @property
    @abstractmethod
    def output_dim(self):
        """The output dimension of the model."""
        pass

    @abstractmethod
    def forward(self, *args, **kwargs):
        """The forward pass of the model."""
        pass
