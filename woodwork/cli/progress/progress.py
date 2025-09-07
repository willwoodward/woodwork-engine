import logging
import multiprocessing
from rich.console import Console, Group
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    ProgressColumn,
    SpinnerColumn,
    Task,
)
from rich.text import Text
from rich.table import Column
from rich.live import Live
import time
from datetime import timedelta
from typing import Dict, List, Callable

from woodwork.components.component import component
from woodwork.types import Update

log = logging.getLogger(__name__)


def worker(component, queue, component_func: Callable):
    component_func(component, queue)


class SpinnerOrCheckColumn(ProgressColumn):
    def __init__(self):
        super().__init__()
        self.spinner = SpinnerColumn(style="cyan")
        self._renderable_cache: Dict[int, tuple[float, Text]] = {}

    def render(self, task: Task) -> Text:
        # Use caching to avoid flickering
        current_time = time.time()
        last_time, _ = self._renderable_cache.get(task.id, (0.0, None))

        # Only update spinner frame if enough time passed
        if current_time - last_time >= 0.1 or task.finished:
            if task.finished:
                renderable = Text("✅", style="green")
            else:
                renderable = self.spinner.render(task)
            self._renderable_cache[task.id] = (current_time, renderable)

        return self._renderable_cache[task.id][1]

    def get_table_column(self) -> Column:
        return Column(no_wrap=True, width=2)


def component_progression_display(
    console, components: List[component], queue: multiprocessing.Queue, present_verb: str
):
    progress = Progress(
        TextColumn("[grey23]|-", justify="right"),
        SpinnerOrCheckColumn(),
        TextColumn("[bold blue]{task.fields[component_name]}", justify="left"),
        BarColumn(bar_width=None, complete_style="grey50", finished_style="grey50", style="grey23"),
        TextColumn("[grey23]{task.percentage:>3.0f}%"),
        TextColumn("[grey23]{task.fields[elapsed]}"),
        expand=True,
    )

    # Register tasks alphabetically
    start_times = {}
    tasks = {}
    for name in sorted(list(map(lambda x: x.name, components))):
        task_id = progress.add_task(
            "",
            component_name=name,
            elapsed="0:00:00",
            total=100.0,
        )
        tasks[name] = task_id
        tasks[name] = task_id
        start_times[name] = time.time()

    done_count = 0

    layout = Group(Text(f"Components {present_verb}...", style="bold white"), progress)
    completed = True
    with Live(layout, console=console, refresh_per_second=10):
        while done_count < len(components):
            try:
                update: Update = queue.get(timeout=0.1)  # small timeout to keep loop alive
                task_id = tasks[update.component_name]
                if update.component_name == "_error":
                    completed = False
                    break
                if update.progress >= 50:
                    done_count += 1
                    elapsed_seconds = int(time.time() - start_times[update.component_name])
                    elapsed_str = str(timedelta(seconds=elapsed_seconds))
                    progress.update(
                        task_id,
                        completed=100,
                        component_name=f"[green]{update.component_name}[/green]",
                        elapsed=elapsed_str,
                    )

                progress.update(task_id, completed=update.progress)

            except:
                pass

            # Update elapsed time
            for component_name, task_id in tasks.items():
                task = progress.tasks[task_id]
                if not task.finished:
                    elapsed_seconds = int(time.time() - start_times[component_name])
                    elapsed_str = str(timedelta(seconds=elapsed_seconds))
                    progress.update(task_id, elapsed=elapsed_str)
    return completed


def parallel_func_apply(
    components: List[component], parallel_func: Callable, component_func: Callable, past_verb: str, present_verb: str
):
    queue = multiprocessing.Queue()

    # Start processes
    processes = []
    for name in components:
        p = multiprocessing.Process(target=worker, args=(name, queue, parallel_func))
        p.start()
        processes.append(p)

    console = Console()

    completed = component_progression_display(console, components, queue, present_verb)

    for p in processes:
        p.join()

    for comp in components:
        component_func(comp, queue)

    if completed:
        console.print(f"[bold green]All components {past_verb} successfully![/bold green]")
    else:
        console.print(f"[bold red]Components {past_verb} successfully![/bold red]")


async def deploy_components(deployments: dict):
    for deployment in deployments.values():
        await deployment.deploy()
