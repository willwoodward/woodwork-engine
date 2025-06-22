from woodwork.components.component import component


class Registry:
    """
    A simple registry to hold references to various components.
    This can be used to register and retrieve components by name.
    """

    def __init__(self):
        self._registry = {}

    def register(self, name: str, component: component):
        """Register a component with a given name."""
        self._registry[name] = component

    def get(self, name: str) -> component | None:
        """Retrieve a component by its name."""
        return self._registry.get(name)

    def __contains__(self, name: str) -> bool:
        """Check if a component is registered under the given name."""
        return name in self._registry


_registry = None


def get_registry():
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry
