import ast
import os
import logging
from importlib import util

from woodwork.helper_functions import format_kwargs
from woodwork.components.apis.api import api

log = logging.getLogger(__name__)


class functions(api):
    def __init__(self, path: str, **config):
        format_kwargs(config, path=path, type="functions")
        super().__init__(**config)
        log.debug("Configuring API with %s and path %s", config, path)

        self._path = path
        self._generate_docs(path)

        log.debug("API configured.")

    def _get_type_hint(self, annotation):
        """Helper function to convert AST annotation to a string."""
        if annotation is None:
            return None
        if isinstance(annotation, ast.Name):
            return annotation.id  # Handles simple types like int, str, etc.
        elif isinstance(annotation, ast.Subscript):
            # Handles types like List[int], Optional[str], etc.
            value = self._get_type_hint(annotation.value)
            slice_value = self._get_type_hint(annotation.slice)
            return f"{value}[{slice_value}]"
        elif isinstance(annotation, ast.Attribute):
            # Handles qualified types like typing.List, Optional, etc.
            return f"{annotation.value.id}.{annotation.attr}"
        return None

    def _generate_docs(self, file_path):
        with open(file_path, "r") as file:
            tree = ast.parse(file.read(), filename=file_path)

        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                docstring = ast.get_docstring(node)
                parameters = []

                # Iterate over the function's arguments and get their names and type hints
                for arg in node.args.args:
                    param_name = arg.arg
                    param_type = self._get_type_hint(arg.annotation)
                    parameters.append({"name": param_name, "type_hint": param_type})

                # Get the return type hint
                return_type = self._get_type_hint(node.returns)

                functions.append(
                    {
                        "name": node.name,
                        "docstring": docstring,
                        "parameters": parameters,
                        "return_type": return_type,
                    }
                )

        self._documentation = ""
        for func in functions:
            params = ", ".join([f"{param['name']}: {param['type_hint']}" for param in func["parameters"]])

            self._documentation += f"[FUNCTION] {func['name']}({params}) -> {func['return_type']}\n"
            self._documentation += f"[DOCUMENTATION] {func['docstring']}\n"

        self._documentation += "Call the functions by specifying only the function name as the action, and the arguments as a dictionary of kwargs."
        log.debug(self.description)

    def _dynamic_import(self):
        module_path = os.path.join(os.getcwd(), f"{self._path}")

        log.debug(f"[MODULE_PATH] {module_path}")
        spec = util.spec_from_file_location(self._path, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {module_path}")
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)  # ty:ignore[possibly-unbound-attribute]
        return module

    def input(self, function_name: str, inputs: dict):
        module = self._dynamic_import()

        func = getattr(module, function_name)
        return func(**inputs)

    @property
    def description(self):
        return self._documentation
