import json
import logging
import logging.config
import pathlib
import sys
import multiprocessing
from dataclasses import dataclass
from rich.console import Console, Group
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    ProgressColumn,
    SpinnerColumn,
    Task,
)
from rich.text import Text
from rich.table import Column
from rich.live import Live

from woodwork import config_parser, dependencies, argument_parser
from woodwork import helper_functions
from woodwork.errors import WoodworkError, ParseError
from woodwork.helper_functions import set_globals
from woodwork.interfaces.intializable import Initializable
from woodwork.interfaces.startable import Startable
from woodwork.registry import get_registry
from woodwork.generate_exports import generate_exported_objects_file

from . import globals

log = logging.getLogger(__name__)

@dataclass
@dataclass
class Update:
    """
    Represents an update in progress.

    :param progress: Progress as a number between 0 and 100.
    :param component: Reference to the component being updated.
    """
    progress: float
    component_name: str

def custom_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, WoodworkError):
        print(f"{exc_value}")
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def start_component(component: Startable, queue):
    queue.put(Update(progress=0, component_name=component.name))
    component.start(config={})
    queue.put(Update(progress=100, component_name=component.name))

def worker(component, queue):
    start_component(component, queue)

def monitor_progress(queue, total_components):
    finished = 0
    while finished < total_components:
        msg: Update = queue.get()
        if msg.progress == 100:
            finished += 1

# Animated spinner or check
from typing import Dict
import time

class SpinnerOrCheckColumn(ProgressColumn):
    def __init__(self):
        super().__init__()
        self.spinner = SpinnerColumn(style="cyan")
        self._renderable_cache: Dict[int, tuple[float, Text]] = {}

    def render(self, task: Task) -> Text:
        # Use caching to avoid flickering
        current_time = time.time()
        last_time, last_renderable = self._renderable_cache.get(task.id, (0.0, None))

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


def init_component(component: Initializable):
    component.init(config={})


def main(args) -> None:
    sys.excepthook = custom_excepthook
    registry = get_registry()

    # Set a delineator for a new application run in log file
    log.debug("\n%s NEW LOG RUN %s\n", "=" * 60, "=" * 60)

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

        initializable_components = list(filter(lambda x: isinstance(x, Initializable), config_parser.task_m._tools))
        with multiprocessing.Pool() as pool:
            pool.map(init_component, initializable_components)

        for component in config_parser.task_m._tools:
            if isinstance(component, Initializable):
                component.init()
        generate_exported_objects_file(registry=registry)
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
    startable_components = list(filter(lambda x: isinstance(x, Startable), config_parser.task_m._tools))
    queue = multiprocessing.Queue()

    # Start processes
    processes = []
    for name in startable_components:
        p = multiprocessing.Process(target=worker, args=(name, queue))
        p.start()
        processes.append(p)

    console = Console()

    progress = Progress(
        TextColumn("|-", justify="right"),
        SpinnerOrCheckColumn(),
        TextColumn("[bold blue]{task.fields[component_name]}", justify="left"),
        BarColumn(bar_width=None),
        TextColumn("[grey58]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        expand=True,
    )

    # Register tasks alphabetically
    tasks = {}
    for name in sorted(list(map(lambda x: x.name, startable_components))):
        task_id = progress.add_task(
            "",
            component_name=name,
            total=100.0,
        )
        tasks[name] = task_id

    done_count = 0

    layout = Group(
        Text("Components Starting…", style="bold white"),
        progress
    )

    with Live(layout, console=console, refresh_per_second=10):
        while done_count < len(startable_components):
            update: Update = queue.get()
            if update.progress == 100:
                done_count += 1

            task_id = tasks[update.component_name]
            progress.update(task_id, completed=update.progress)

    for p in processes:
        p.join()

    console.print("[bold green]All components started successfully![/bold green]")

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
