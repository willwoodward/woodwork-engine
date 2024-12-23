from abc import ABC

from woodwork.components.component import component
from woodwork.interfaces.tool_interface import tool_interface


class api(component, tool_interface, ABC):
    def __init__(self, name, config):
        super().__init__(name, "api")
