from abc import ABC

from woodwork.components.component import Component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.utils import format_kwargs


class Core(Component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="core")
        super().__init__(**config)
