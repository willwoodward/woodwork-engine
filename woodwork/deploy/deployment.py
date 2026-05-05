from typing import List

from woodwork.components.component import component


class Deployment:
    def __init__(self, name: str, components: List[component], **config):
        self.name = name
        self.components = components
