import ast
import importlib
import os

from woodwork.helper_functions import print_debug
from woodwork.components.apis.api import api

class functions(api):
    def __init__(self, name, config):
        print_debug("Configuring API...")
        super().__init__(name, config)
        
        self._config_checker(name, ["path"], config)
        
        self._path = config["path"]
        self._generate_docs(self._path)
        
        print_debug("API configured.")

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
        with open(file_path, 'r') as file:
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
                    parameters.append({
                        'name': param_name,
                        'type_hint': param_type
                    })
                
                # Get the return type hint
                return_type = self._get_type_hint(node.returns)

                functions.append({
                    'name': node.name,
                    'docstring': docstring,
                    'parameters': parameters,
                    'return_type': return_type
                })
        
        self._documentation = ""
        for func in functions:
            params = ', '.join([f"{param['name']}: {param['type_hint']}" for param in func['parameters']])

            self._documentation += f"[FUNCTION] {func['name']}({params}) -> {func['return_type']}\n"
            self._documentation += f"[DOCUMENTATION] {func['docstring']}\n"
            
            print_debug(self.describe())

    def _dynamic_import(self):
        module_path = os.path.join(os.getcwd(), f"{self._path}")
        
        print_debug(f"[MODULE_PATH] {module_path}")
        spec = importlib.util.spec_from_file_location(self._path, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def call(self, function_name: str, inputs):
        module = self._dynamic_import()

        func = getattr(module, function_name)
        return func(**inputs)

    def describe(self):
        return self._documentation