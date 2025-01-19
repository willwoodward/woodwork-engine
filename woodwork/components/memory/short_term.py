from woodwork.components.memory.memory import memory
from woodwork.helper_functions import format_kwargs


class short_term(memory):
    def __init__(self, **config):
        format_kwargs(config, type="short_term")
        super().__init__(**config)

        self._data = ""

    @property
    def data(self):
        return self._data

    def add(self, text: str):
        self._data = self._data + f"{text}\n"

    def clear(self):
        self._data = ""
