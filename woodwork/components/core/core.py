from abc import ABC

from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.helper_functions import format_kwargs


class core(component, tool_interface, ABC):
    def __init__(self, **config):
        format_kwargs(config, component="core")
        super().__init__(**config)
