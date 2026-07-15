"""Primitive types for the woodwork Python API."""

import os


class Env(str):
    """Read an environment variable eagerly at construction time.

    Subclasses :class:`str` so it is transparent to any component that
    accepts a plain ``str`` (e.g. ``api_key``).

    Raises :class:`KeyError` at construction time if the variable is not set,
    giving a clear error message before the component graph is built.
    """

    def __new__(cls, key: str) -> "Env":
        try:
            value = os.environ[key]
        except KeyError:
            raise KeyError(
                f"Environment variable '{key}' is not set. "
                "Call load_envfile() before constructing components, "
                "or set the variable in your shell."
            )
        instance = super().__new__(cls, value)
        instance.key = key
        return instance

    def __repr__(self) -> str:
        return f"Env({self.key!r})"


class File:
    """Reference to a file path (e.g. a system-prompt text file).

    Pass a :class:`File` wherever a component accepts a prompt or file path.
    The file is read lazily when the component is started.
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def __str__(self) -> str:
        return self.path

    def __repr__(self) -> str:
        return f"File({self.path!r})"

    def read(self) -> str:
        """Read and return the file contents."""
        with open(self.path) as fh:
            return fh.read()
