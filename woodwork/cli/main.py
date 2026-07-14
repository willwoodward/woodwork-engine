import asyncio
import json
import logging
import logging.config
import pathlib
import sys

from woodwork.config import dependencies
from woodwork.utils import helper_functions
from woodwork.cli import argument_parser
from woodwork.config import parser as config_parser
from woodwork.config import operations as config_operations
from woodwork.config.factory import build_components
from woodwork.utils.errors.errors import ParseError
from woodwork.utils.helper_functions import set_globals
from woodwork.deploy.registry import get_registry
from woodwork.deploy import Deployer
from woodwork.deploy.generate_exports import generate_exported_objects_file
from .progress.progress import parallel_func_apply
from .progress.lifecycles import start_component
from rich.console import Console
from woodwork.cli.setup_defaults import copy_prompts
from woodwork.cli.cleanup import clean_all
from woodwork.utils import get_package_directory
from woodwork.core.runtime import AsyncRuntime

import woodwork.globals as globals

log = logging.getLogger(__name__)


def parse_and_validate_config():
    """Parse .ww configuration files and return (commands, components)."""
    import time

    console = Console()
    console.print("Parsing configuration...", style="dim", highlight=False)
    start = time.time()
    dependencies.activate_virtual_environment()

    import os
    with open(os.path.join(os.getcwd(), "main.ww")) as f:
        ww_text = f.read()
    commands = config_parser.parse(ww_text)
    components, dep_map = build_components(commands)

    console.print(f"✓ Config parsed in {time.time() - start:.1f}s", style="dim", highlight=False)
    return components, dep_map


def generate_exports():
    """Generate exported objects file for the registry."""
    import time

    console = Console()
    start = time.time()
    registry = get_registry()
    generate_exported_objects_file(registry=registry)
    console.print(f"✓ Exports generated in {time.time() - start:.1f}s", style="dim", highlight=False)


def deploy_containers():
    """Deploy Docker containers for components that need them."""
    import time

    console = Console()
    console.print("Deploying containers...", style="dim", highlight=False)
    start = time.time()
    deployer = Deployer()
    deployer.main()
    console.print(f"✓ Containers deployed in {time.time() - start:.1f}s", style="dim", highlight=False)


def start_components(components):
    """Start all components with progress bar display."""
    console = Console()
    console.print(f"Starting {len(components)} components...", style="dim", highlight=False)
    parallel_func_apply(components, start_component, "started", "starting")


def start_runtime(components, dep_map):
    """Start the AsyncRuntime."""
    async def _run():
        runtime = AsyncRuntime()
        try:
            await runtime.start(components, dep_map)
        except KeyboardInterrupt:
            pass
        finally:
            await runtime.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        Console().print("\n[dim]✓ Shutdown complete[/dim]", highlight=False)


def app_entrypoint(args):
    """Main application entrypoint for Woodwork CLI."""
    get_registry()
    log.debug("\n%s NEW LOG RUN %s\n", "=" * 60, "=" * 60)

    try:
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

    if getattr(args, "clean", False):
        log.info("--clean flag provided: running cleanup and exiting.")
        clean_all()
        return

    log.debug("Arguments: %s", args)

    match args.mode:
        case "run":
            log.debug("Mode set to 'run'.")
        case "debug":
            log.debug("Mode set to 'debug'.")
            log.warning(
                "Mode is set to 'debug'. This mode has been deprecated. "
                "Please use 'run' mode instead. Defaulting to 'run' mode.",
            )
        case "embed":
            log.debug("Mode set to 'embed'.")
        case "clear":
            log.debug("Mode set to 'clear'.")
        case _:
            pass

    log.debug("Globals set: Mode = %s", globals.global_config["mode"])
    copy_prompts()

    if args.init is not None:
        options = {"isolated": False, "all": False}
        if args.init == "isolated":
            options["isolated"] = True
        elif args.init == "all":
            options["isolated"] = True
            options["all"] = True
        dependencies.init(options)
        return

    if args.gui is not None:
        if args.gui == "run":
            log.debug("GUI is set to run.")
            components, _ = parse_and_validate_config()
            from woodwork.gui.gui import GUI
            gui = GUI(components)
            gui.run()
            return
        elif args.gui == "fastapi":
            log.debug("FastAPI GUI is set to run.")
            from woodwork.gui.fastapi_gui_server import start_gui_server
            asyncio.run(start_gui_server())
            return

    if args.workflow != "none":
        if args.mode in {"run", "debug"}:
            log.warning(
                "Possible conflict: Mode is %s which conflicts with %s Workflow.",
                args.mode,
                args.workflow,
            )
        set_globals(inputs_activated=False)

    # Phase 1: Parse
    components, dep_map = parse_and_validate_config()
    generate_exports()

    # Phase 2: Deploy
    deploy_containers()

    # Phase 3: Start components
    start_components(components)

    # Phase 4: Mode-specific operations
    match args.mode:
        case "embed":
            config_operations.embed_all()
        case "clear":
            config_operations.clear_all()
        case _:
            pass

    match args.workflow:
        case "remove":
            config_operations.delete_action_plan(args.target)
        case "find":
            config_operations.find_action_plan(args.target)
        case _:
            pass

    # Phase 5: Run runtime
    start_runtime(components, dep_map)


def cli_entrypoint() -> None:
    """Initializes logging and runs the main Woodwork CLI entrypoint."""
    args = argument_parser.parse_args()

    if args.logConfig is not None:
        config_file = pathlib.Path(args.logConfig)
    else:
        config_file = pathlib.Path(get_package_directory()) / "config" / "log_config.json"

    try:
        with pathlib.Path.open(config_file) as f_in:
            config = json.load(f_in)
    except FileNotFoundError:
        sys.exit(1)

    log_directory = pathlib.Path(config["handlers"]["file"]["filename"].split("/")[0])
    if not log_directory.exists():
        log_directory.mkdir()

    logging.config.dictConfig(config)
    app_entrypoint(args)
