import json
import logging
import logging.config
import pathlib
import sys
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
from typing import Dict, List, Callable, Optional
import threading
import warnings

from woodwork import config_parser, dependencies, argument_parser
from woodwork import helper_functions
from woodwork.components.component import component
from woodwork.errors import WoodworkError, ParseError
from woodwork.helper_functions import set_globals
from woodwork.interfaces.intializable import ParallelInitializable, Initializable
from woodwork.interfaces.startable import ParallelStartable, Startable
from woodwork.registry import get_registry
from woodwork.types import Update
from woodwork.deployments import Deployer
from woodwork.generate_exports import generate_exported_objects_file

from . import globals

log = logging.getLogger(__name__)


def custom_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, WoodworkError):
        print(f"{exc_value}")
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def parallel_start_component(c: component, queue: multiprocessing.Queue):
    if isinstance(c, ParallelStartable):
        c.parallel_start(queue=queue, config={})

    if isinstance(c, Startable):
        queue.put(Update(progress=67, component_name=c.name))
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
        queue.put(Update(progress=67, component_name=c.name))
    else:
        queue.put(Update(progress=100, component_name=c.name))


def init_component(c: component, queue: multiprocessing.Queue):
    if isinstance(c, Initializable):
        c.init(queue=queue, config={})
    queue.put(Update(progress=100, component_name=c.name))


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
    console: Console,
    components: List,
    queue: multiprocessing.Queue,
    present_verb: str,
    component_func: Callable,
):
    progress = Progress(
        TextColumn("[grey23]|-", justify="right"),
        SpinnerOrCheckColumn(),
        TextColumn("[bold blue]{task.fields[display_name]}", justify="left"),
        BarColumn(bar_width=None, complete_style="grey50", finished_style="grey50", style="grey23"),
        TextColumn("[grey23]{task.percentage:>3.0f}%"),
        TextColumn("[grey23]{task.fields[elapsed]}"),
        expand=True,
    )

    start_times = {}
    finished_times = {}
    finished_flags = {}
    tasks = {}

    # Create progress tasks in sorted order by component name
    for comp in sorted(components, key=lambda c: c.name):
        name = comp.name
        task_id = progress.add_task(
            "",
            component_name=name,
            display_name=name,
            elapsed="0:00:00",
            total=100.0,
        )
        tasks[name] = task_id
        start_times[name] = time.time()
        finished_flags[name] = False

    layout = Group(Text(f"Components {present_verb}...", style="bold white"), progress)
    completed = True

    # Start all component threads concurrently
    threads = []
    for comp in components:
        thread = threading.Thread(target=component_func, args=(comp, queue), daemon=True)
        thread.start()
        threads.append((comp, thread))

    with Live(layout, console=console, refresh_per_second=10):
        while True:
            # Process all available updates in the queue
            try:
                while True:
                    update = queue.get(timeout=0.1)
                    if update.component_name == "_error":
                        completed = False
                        return completed

                    task_id = tasks[update.component_name]
                    progress.update(task_id, completed=update.progress)

                    # Immediately finalize finished components
                    if update.progress >= 100 and not finished_flags[update.component_name]:
                        finished_flags[update.component_name] = True
                        finished_times[update.component_name] = time.time()

                        elapsed_seconds = int(
                            finished_times[update.component_name] - start_times[update.component_name]
                        )
                        elapsed_str = str(timedelta(seconds=elapsed_seconds))

                        progress.update(
                            task_id,
                            completed=100,
                            display_name=f"[green]{update.component_name}[/green]",
                            elapsed=elapsed_str,
                            refresh=True,
                        )

            except:
                # No more updates currently in the queue
                pass
            
            # Update elapsed time only for unfinished components
            for cname, tid in tasks.items():
                if finished_flags[cname]:
                    continue
                elapsed_seconds = int(time.time() - start_times[cname])
                elapsed_str = str(timedelta(seconds=elapsed_seconds))
                progress.update(tid, elapsed=elapsed_str)
            
            # Exit when all threads are finished
            if all(not thread.is_alive() for _, thread in threads):
                break

    # Join all threads after finishing
    for _, thread in threads:
        thread.join()

    return completed


def parallel_func_apply(
    components: List[component], parallel_func: Callable, component_func: Callable, past_verb: str, present_verb: str, queue: Optional[multiprocessing.Queue] = None, health_thread: Optional[threading.Thread] = None
):
    if queue is None:
        queue = multiprocessing.Queue()

    if health_thread is not None:
        health_thread.start()

    # Start processes
    processes = []
    for name in components:
        p = multiprocessing.Process(target=worker, args=(name, queue, parallel_func))
        p.start()
        processes.append(p)

    console = Console()
    completed = component_progression_display(console, components, queue, present_verb, component_func)

    for p in processes:
        p.join()
    
    if health_thread is not None:
        health_thread.join()

    if completed:
        console.print(f"[bold green]All components {past_verb} successfully![/bold green]")
    else:
        console.print(f"[bold red]Components {past_verb} successfully![/bold red]")


async def deploy_components(deployments: dict):
    for deployment in deployments.values():
        await deployment.deploy()


def main(args) -> None:
    sys.excepthook = custom_excepthook
    registry = get_registry()

    # Set a delineator for a new application run in log file
    log.debug("\n%s NEW LOG RUN %s\n", "=" * 60, "=" * 60)

    # Langchain library has deprecated verbose import from root module
    # and it causes a warning to be printed to the console.
    warnings.filterwarnings(
        "ignore",
        message="Importing verbose from langchain root module is no longer supported"
    )

    try:
        # Confirm that there are no known conflicts in the arguments before doing anything else
        argument_parser.check_parse_conflicts(args)
    except ParseError as e:
        log.critical("ParseError: %s", e)
        return

    if args.version:
        version_from_toml = helper_functions.get_version_from_pyproject(
            str(pathlib.Path(__file__).parent.parent / "pyproject.toml")
        )
        print(f"Woodwork version: {version_from_toml}")
        return

    log.debug("Arguments: %s", args)

    # Set globals based on flags before execution
    match args.mode:
        case "run":
            log.debug("Mode set to 'run'.")
        case "debug":
            log.debug("Mode set to 'debug'.")
            log.warning(
                "Mode is set to 'debug'. This mode has been deprecated and will be removed in a future release. "
                "You can access debug information by setting the logging level to DEBUG in your logging configuration. "
                "Please use 'run' mode instead. Defaulting to 'run' mode.",
            )
        case "embed":
            log.debug("Mode set to 'embed'.")
        case "clear":
            log.debug("Mode set to 'clear'.")
        case _:
            # ArgParse will SysExit if choice not in list
            pass

    log.debug(
        "Globals set: Mode = %s",
        globals.global_config["mode"],
    )

    if args.init is not None:
        options = {"isolated": False, "all": False}
        if args.init == "isolated":
            options["isolated"] = True
            log.debug("Initialization mode set to 'isolated'.")
        elif args.init == "all":
            options["isolated"] = True
            options["all"] = True
            log.debug("Initialization mode set to 'all'.")
        dependencies.init(options)

        # Run the initialization methods
        config_parser.main_function(registry=registry)

        components = config_parser.task_m._tools
        parallel_func_apply(components, parallel_init_component, init_component, "initialized", "initializing")
        generate_exported_objects_file(registry=registry)
        return

    if args.gui is not None:
        if args.gui == "run":
            log.debug("GUI is set to run.")
            from woodwork.gui.gui import GUI

            gui = GUI()
            gui.run()
            return

    if args.workflow != "none":
        if args.mode in {"run", "debug"}:
            log.debug(
                "Workflow is set to %s, which isn't compatible with %s Mode.",
                args.workflow,
                args.mode,
            )
            log.warning(
                "Possible conflict: Mode is %s which conflicts with %s Workflow.",
                args.mode,
                args.workflow,
            )
        set_globals(inputs_activated=False)

    # Execute the main functionality
    dependencies.activate_virtual_environment()
    config_parser.main_function()
    generate_exported_objects_file(registry=registry)

    # Start all components that implement the Startable interface
    components = config_parser.task_m._tools
    deployer = Deployer()
    queue = multiprocessing.Queue()
    deployer.main()
    
    # Run health check in background thread
    health_thread = threading.Thread(target=deployer.healthy, args=(queue,), daemon=True)

    parallel_func_apply(components, parallel_start_component, start_component, "started", "starting", queue, health_thread)

    # Clean up after execution
    match args.mode:
        case "embed":
            config_parser.embed_all()
        case "clear":
            config_parser.clear_all()
        case _:
            # ArgParse will SysExit if choice not in list
            pass

    match args.workflow:
        case "add":
            config_parser.add_action_plan(args.target)
            log.debug("%s Workflow set with path: %s.", args.workflow, args.target)
        case "remove":
            config_parser.delete_action_plan(args.target)
            log.debug("%s Workflow removed with id: %s.", args.workflow, args.target)
        case "find":
            config_parser.find_action_plan(args.target)
            log.debug("%s Workflow found with query: %s.", args.workflow, args.target)
        case _:
            # ArgParse will SysExit if choice not in list
            pass

    config_parser.task_m.start()
    return


def run_as_standalone_app() -> None:
    """
    Initializes a custom logger based on the configuration file and runs the main function of the Woodwork library.

    This is used to configure logging when ran standalone from any external scripts.
    If a logging configuration file is not found, a default logger is created.
    Do not use this function if you have configured your own logger. Simply call `main()` directly.
    """

    args = argument_parser.parse_args()

    if args.logConfig is not None:
        # If a custom logging configuration file is specified, use it
        config_file = pathlib.Path(args.logConfig)
    else:
        config_file = pathlib.Path(__file__).parent / "config" / "log_config.json"

    try:
        with pathlib.Path.open(config_file) as f_in:
            config = json.load(f_in)
    except FileNotFoundError:
        sys.exit(1)

    # Get the directory for logging as specified in the logging_config.json file to
    # create the log directory if it does not exist. The filename in the config file
    # must be only one folder deep from the root, such as "./logs/", however the
    # directory name can be anything.
    log_directory = pathlib.Path(config["handlers"]["file"]["filename"].split("/")[0])
    if not log_directory.exists():
        log_directory.mkdir()

    logging.config.dictConfig(config)

    main(args)
