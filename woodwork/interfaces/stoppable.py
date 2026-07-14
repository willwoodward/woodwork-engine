from abc import ABC, abstractmethod


class Stoppable(ABC):
    """Interface for components that require async teardown."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the component and release any held resources."""
