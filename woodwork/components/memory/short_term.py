from woodwork.components.memory.memory import Memory
from woodwork.utils import format_kwargs


class ShortTermMemory(Memory):
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
