import ast
import logging
import os
from importlib import util
from typing import Any

from woodwork.utils import format_kwargs
from woodwork.components.apis.api import API

log = logging.getLogger(__name__)


class Functions(API):
    def __init__(self, path: str, **config):
        format_kwargs(config, path=path, type="functions")
        super().__init__(**config)
        log.debug("Configuring Functions API with path %s", path)

        self._path = path
        self._generate_docs(path)

        log.debug("Functions API configured.")

    def _get_type_hint(self, annotation):
        if annotation is None:
            return None
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Subscript):
            value = self._get_type_hint(annotation.value)
            slice_value = self._get_type_hint(annotation.slice)
            return f"{value}[{slice_value}]"
        elif isinstance(annotation, ast.Attribute):
            return f"{annotation.value.id}.{annotation.attr}"
        return None

    def _generate_docs(self, file_path):
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=file_path)

        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                docstring = ast.get_docstring(node)
                parameters = [
                    {"name": arg.arg, "type_hint": self._get_type_hint(arg.annotation)}
                    for arg in node.args.args
                ]
                return_type = self._get_type_hint(node.returns)
                functions.append(
                    {"name": node.name, "docstring": docstring, "parameters": parameters, "return_type": return_type}
                )

        self._documentation = ""
        for func in functions:
            params = ", ".join([f"{p['name']}: {p['type_hint']}" for p in func["parameters"]])
            self._documentation += f"[FUNCTION] {func['name']}({params}) -> {func['return_type']}\n"
            self._documentation += f"[DOCUMENTATION] {func['docstring']}\n"

        self._documentation += (
            "Call the functions by specifying only the function name as the action, "
            "and the arguments as a dictionary of kwargs."
        )
        log.debug(self.description)

    def _dynamic_import(self):
        module_path = os.path.join(os.getcwd(), self._path)
        spec = util.spec_from_file_location(self._path, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {module_path}")
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)  # ty:ignore[possibly-unbound-attribute]
        return module

    def execute(self, function_name: str, inputs: dict) -> Any:
        module = self._dynamic_import()
        func = getattr(module, function_name)
        return func(**inputs)

    # Legacy alias
    def input(self, function_name: str, inputs: dict) -> Any:
        return self.execute(function_name, inputs)

    @property
    def description(self):
        return self._documentation
