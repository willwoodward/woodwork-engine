"""Structural protocols for woodwork components."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    """A callable tool that an agent can invoke."""

    name: str
    description: str

    async def execute(self, action: str, inputs: dict[str, Any]) -> Any: ...


@runtime_checkable
class Component(Protocol):
    """A managed component with a lifecycle."""

    name: str

    async def initialize(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


@runtime_checkable
class Transport(Protocol):
    """Sends calls to a named target and returns the result."""

    async def call(self, target: str, action: str, inputs: dict[str, Any]) -> Any: ...


@runtime_checkable
class WorkflowStore(Protocol):
    """Persists and retrieves recorded agent workflows."""

    async def save(self, workflow: Any) -> None: ...

    async def load_similar(self, query: str, limit: int) -> list[Any]: ...
