from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface
from woodwork.utils import format_kwargs


class mcp(component, tool_interface):
    def __init__(self, **config):
        format_kwargs(config, component="mcp")
        super().__init__(**config)
