from abc import ABC, abstractmethod

from woodwork.components.component import component

class inputs(component):
    def __init__(self, name):
        super().__init__(name, "input")
