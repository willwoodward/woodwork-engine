import queue
import logging

from woodwork.components.component import component
from woodwork.interfaces.startable import Startable
from woodwork.types import Update

log = logging.getLogger(__name__)


def start_component(c: component, q: queue.Queue):
    """Start a component (called in parallel via threading)"""
    # If component implements Startable interface, call start() method
    if isinstance(c, Startable):
        c.start(queue=q, config={})
        if q:
            q.put(Update(progress=50, component_name=c.name))
    else:
        # Component doesn't need starting, mark as complete
        if q:
            q.put(Update(progress=100, component_name=c.name))
