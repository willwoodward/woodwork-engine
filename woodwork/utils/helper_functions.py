import importlib
import importlib.resources as pkg_resources
import os
import logging
import tomli
import inspect
import asyncio

from woodwork.utils.errors import WoodworkError
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


def get_package_directory():
    return pkg_resources.files("woodwork")


def get_prompt(path: str) -> str:
    """Returns the system prompt from the file location specified."""
    if not os.path.isfile(path):
        raise WoodworkError(f"Failed to find the prompt file specified at location: {path}")

    with open(path) as f:
        prompt = f.read()
    return prompt

def sync_async(func, *args, **kwargs):
    """
    Run an async function from synchronous code.
    Falls back gracefully if already inside an event loop.
    """
    if inspect.iscoroutinefunction(func):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # no running loop → safe to use asyncio.run
            return asyncio.run(func(*args, **kwargs))
        else:
            # already in an event loop → use create_task and wait
            return loop.run_until_complete(func(*args, **kwargs))
    else:
        return func(*args, **kwargs)
    

async def maybe_async(func, *args, **kwargs):
    """Helper to call either sync or async functions properly"""
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)