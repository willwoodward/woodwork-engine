from woodwork.components.models.model import model
from woodwork.helper_functions import format_kwargs


class pytorch(model):
    def __init__(self, **config):
        format_kwargs(config, type="pytorch")
        super().__init__(**config)
