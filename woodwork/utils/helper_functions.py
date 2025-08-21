import importlib
import os
import logging
import tomli  # tomli since we support P3.10 and tomllib is not available until P3.11

from woodwork.globals import global_config as config

log = logging.getLogger(__name__)


def set_globals(**kwargs) -> None:
    for key, value in kwargs.items():
        config[key] = value


def import_all_classes(package_name: str) -> bool:
    # Get the package path
    package = importlib.import_module(package_name)
    package_path = package.__path__[0]

    # Traverse directories and import all .py files as modules
    imported_all = True
    for root, _, files in os.walk(package_path):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                # Derive the full module path
                relative_path = os.path.relpath(root, package_path)
                print("RELPATH =", relative_path)
                module_name = os.path.splitext(file)[0]

                if relative_path == ".":
                    full_module_name = f"{package_name}.{module_name}"
                else:
                    full_module_name = f"{package_name}.{relative_path.replace(os.path.sep, '.')}.{module_name}"

                # Import the module
                try:
                    importlib.import_module(full_module_name)
                except ImportError as e:
                    print(f"Could not import {full_module_name}: {e}")
                    imported_all = False

    return imported_all


def get_optional(dictionary: dict, key: str, default=None, type: type | None = None):
    """
    Given the key to look up in a dictionary, assert that the variable is of the correct type.
    Then return either the value, or the default value, or None if this is blank.
    """

    value = dictionary.get(key)

    if value is None:
        return default

    if type is None:
        return value

    if not isinstance(value, type):
        raise TypeError(f"{value} is not of type {type}.")
    return value


def format_kwargs(kwarg_dict, **kwargs) -> None:
    """
    Used to pass mandatory args in the child to the parent, by adding those variables to kwargs.

    Modifies the kwarg_dict in place.
    """

    for kwarg in kwargs:
        kwarg_dict[kwarg] = kwargs[kwarg]
    return


def get_version_from_pyproject(pyproject_path="pyproject.toml") -> str:
    """
    Get the version from the pyproject.toml file.
    """
    with open(pyproject_path, "rb") as f:
        data = tomli.load(f)

    return data["project"]["version"]
