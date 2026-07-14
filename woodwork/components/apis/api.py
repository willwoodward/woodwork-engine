from abc import ABC

from woodwork.components.component import Component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.utils import format_kwargs


class API(Component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="api")
        super().__init__(**config)
