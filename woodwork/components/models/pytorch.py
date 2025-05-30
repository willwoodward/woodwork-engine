import torch
import importlib

from woodwork.components.models.model import model
from woodwork.helper_functions import format_kwargs

def import_class_from_path(path):
    """Dynamically import a class from a string path like 'package.module.ClassName'."""
    module_path, class_name = path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class pytorch(model):
    def __init__(self, model_weights, model_code, **config):
        format_kwargs(config, model_weights=model_weights, type="pytorch")
        super().__init__(**config)
        Model = import_class_from_path(model_code)
        self.model = Model()
        self.model.load_state_dict(torch.load(model_weights))
        self.model.eval()
    
    @property
    def input_shape(self):
        return (10, 3, 28, 28)
    
    @property
    def output_shape(self):
        return self.model.output_shape

    def forward(self):
        input_tensor = torch.randn(self.input_shape)
        with torch.no_grad():
            out = self.model(input_tensor)
            print(out.shape)
            return

    def input(self, function_name: str, inputs: dict):
        func = None
        if function_name == "forward":
            func = self.forward

        if func is None:
            return

        return func(**inputs)

    @property
    def description(self):
        return f"A loaded PyTorch model, which can be used for inference by running the forward method, with an empty dictionary as input."