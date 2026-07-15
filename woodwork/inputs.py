"""Convenience re-exports for input components.

Example::

    from woodwork.inputs import CommandLine, API

    cli = CommandLine(name="cli")
"""

from woodwork.components.inputs.command_line import CommandLineInput
from woodwork.components.inputs.api_input import APIInput


class CommandLine(CommandLineInput):
    """Command-line input component for the woodwork Python API."""

    def __init__(self, name: str, **kwargs):
        super().__init__(name=name, component="input", **kwargs)


class API(APIInput):
    """API / WebSocket input component for the woodwork Python API."""

    def __init__(self, name: str = "api_input", **kwargs):
        super().__init__(name=name, component="input", **kwargs)


__all__ = ["CommandLine", "API"]
