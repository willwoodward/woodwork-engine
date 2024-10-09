from woodwork.components.memory.memory import memory

class short_term(memory):
    def __init__(self, name, config):
        super().__init__(name, config)

        self._data = ""
    
    @property
    def data(self):
        return self._data
    
    def add(self, text: str):
        self._data = self._data + f"\n{text}"
    
    def clear(self):
        self._data = ""
