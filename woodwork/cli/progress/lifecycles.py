import multiprocessing

from woodwork.components.component import component
from woodwork.interfaces.intializable import ParallelInitializable, Initializable
from woodwork.interfaces.startable import ParallelStartable, Startable
from woodwork.types import Update

def parallel_start_component(c: component, queue: multiprocessing.Queue):
    if isinstance(c, ParallelStartable):
        c.parallel_start(queue=queue, config={})

    if isinstance(c, Startable):
        queue.put(Update(progress=50, component_name=c.name))
    else:
        queue.put(Update(progress=100, component_name=c.name))


def start_component(c: component, queue: multiprocessing.Queue):
    if isinstance(c, Startable):
        c.start(queue=queue, config={})
    queue.put(Update(progress=100, component_name=c.name))


def parallel_init_component(c: component, queue: multiprocessing.Queue):
    if isinstance(c, ParallelInitializable):
        c.parallel_init(queue=queue, config={})

    if isinstance(c, Initializable):
        queue.put(Update(progress=50, component_name=c.name))
    else:
        queue.put(Update(progress=100, component_name=c.name))


def init_component(c: component, queue: multiprocessing.Queue):
    if isinstance(c, Initializable):
        c.init(queue=queue, config={})
    queue.put(Update(progress=100, component_name=c.name))
