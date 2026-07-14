from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from woodwork.components.component import Component


class Deployment:
    def __init__(self, name: str, components: "List[Component]", **config):
        self.name = name
        self.components = components
