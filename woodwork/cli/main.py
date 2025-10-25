import json
import logging
import logging.config
import pathlib
import sys

from woodwork.parser import dependencies
from woodwork.utils import helper_functions
from woodwork.cli import argument_parser
from woodwork.parser import config_parser
from woodwork.utils.errors.errors import ParseError
from woodwork.utils.helper_functions import set_globals
from woodwork.deployments.registry import get_registry
from woodwork.deployments import Deployer
from woodwork.deployments.generate_exports import generate_exported_objects_file
from .progress.progress import parallel_func_apply
from .progress.lifecycles import start_component
from rich.console import Console
from woodwork.cli.setup_defaults import copy_prompts
from woodwork.cli.cleanup import clean_all
from woodwork.utils import get_package_directory

import woodwork.globals as globals

log = logging.getLogger(__name__)


def parse_and_validate_config():
    """Parse .ww configuration files and return components."""
    import time
    console = Console()

    console.print("Parsing configuration...", style="dim", highlight=False)
    start = time.time()
    dependencies.activate_virtual_environment()
    config_parser.main_function()
    console.print(f"✓ Config parsed in {time.time() - start:.1f}s", style="dim", highlight=False)

    return config_parser.task_m._tools


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
    import time
    console = Console()

    console.print(f"Starting {len(components)} components...", style="dim", highlight=False)
    start = time.time()
    parallel_func_apply(components, start_component, "started", "starting")


def start_runtime(components):
    """Start the appropriate runtime (async or task master)."""
    import time
    console = Console()

    if globals.global_config.get("message_bus_active", False):
        _start_async_runtime(components)
    else:
        _start_task_master_runtime()


def _start_async_runtime(components):
    """Start async runtime with distributed message bus orchestration."""
    from woodwork.core.async_runtime import AsyncRuntime
    import asyncio
    from rich.spinner import Spinner
    from rich.live import Live
    import sys

    console = Console()

    component_config = {}
    for tool in components:
        component_config[tool.name] = {
            "component": tool.__class__.__name__.lower(),
            "type": getattr(tool, 'type', 'unknown'),
            "object": tool
        }

    async def start_async_runtime():
        runtime = AsyncRuntime()
        try:
            await runtime.start({"components": components, "component_configs": component_config})
        except KeyboardInterrupt:
            print("\n", flush=True)
            sys.stderr.flush()

            with Live(Spinner("dots", text="[dim]Shutting down...[/dim]"), console=console, refresh_per_second=10, redirect_stdout=False, redirect_stderr=False, transient=False):
                await runtime.stop()
        except Exception as e:
            log.error("Runtime error: %s", e)
            await runtime.stop()
            raise

    try:
        asyncio.run(start_async_runtime())
    except KeyboardInterrupt:
        pass


def _start_task_master_runtime():
    """Start traditional task master orchestration."""
    print("🔧 DEBUG: Traditional mode - using TaskMaster orchestration")
    config_parser.task_m.start()


def app_entrypoint(args):
    """Main application entrypoint for Woodwork CLI.

    Handles different execution modes:
    - --init: Install dependencies for .ww config files
    - --gui: Run GUI interface (FastAPI or legacy)
    - --clean: Clean up resources
    - default: Run Woodwork with configured components
    """
    registry = get_registry()

    # Set a delineator for a new application run in log file
    log.debug("\n%s NEW LOG RUN %s\n", "=" * 60, "=" * 60)

    # ============================================================================
    # VALIDATION: Check arguments before doing anything else
    # ============================================================================
    try:
        argument_parser.check_parse_conflicts(args)
    except ParseError as e:
        log.critical("ParseError: %s", e)
        return

    # ============================================================================
    # UTILITY MODES: Handle simple commands that don't require full initialization
    # ============================================================================
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

    # ============================================================================
    # CONFIGURATION: Set up globals and copy default prompts
    # ============================================================================
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
            pass

    log.debug("Globals set: Mode = %s", globals.global_config["mode"])
    copy_prompts()

    # ============================================================================
    # INIT MODE: Install dependencies only (no component initialization)
    # ============================================================================
    if args.init is not None:
        options = {"isolated": False, "all": False}
        if args.init == "isolated":
            options["isolated"] = True
            log.debug("Initialization mode set to 'isolated'.")
        elif args.init == "all":
            options["isolated"] = True
            options["all"] = True
            log.debug("Initialization mode set to 'all'.")

        # Only install dependencies - no parsing, no components, no initialization
        dependencies.init(options)
        return

    # ============================================================================
    # GUI MODE: Run web interface
    # ============================================================================
    if args.gui is not None:
        if args.gui == "run":
            log.debug("GUI is set to run.")
            dependencies.activate_virtual_environment()
            config_parser.main_function()
            from woodwork.gui.gui import GUI

            gui = GUI(config_parser.task_m)
            gui.run()
            return
        elif args.gui == "fastapi":
            log.debug("FastAPI GUI is set to run.")
            dependencies.activate_virtual_environment()
            # Import and run the FastAPI GUI server
            import asyncio
            from woodwork.gui.fastapi_gui_server import start_gui_server

            asyncio.run(start_gui_server())
            return

    # ============================================================================
    # WORKFLOW CONFIGURATION: Handle workflow-specific settings
    # ============================================================================
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

    # ============================================================================
    # MAIN EXECUTION: Build, deploy, and run
    # ============================================================================
    # Phase 1: Build - Parse configuration and generate exports
    components = parse_and_validate_config()
    generate_exports()

    # Phase 2: Deploy - Start Docker containers
    deploy_containers()

    # Phase 3: Start - Initialize all components
    start_components(components)

    # ============================================================================
    # POST-EXECUTION: Handle mode-specific cleanup and operations
    # ============================================================================
    match args.mode:
        case "embed":
            config_parser.embed_all()
        case "clear":
            config_parser.clear_all()
        case _:
            pass

    # Handle workflow operations (add/remove/find action plans)
    match args.workflow:
        case "add":
            pass
        case "remove":
            config_parser.delete_action_plan(args.target)
            log.debug("%s Workflow removed with id: %s.", args.workflow, args.target)
        case "find":
            config_parser.find_action_plan(args.target)
            log.debug("%s Workflow found with query: %s.", args.workflow, args.target)
        case _:
            pass

    # ============================================================================
    # RUNTIME: Start the appropriate orchestration system
    # ============================================================================
    # Phase 4: Run - Start the runtime event loop
    start_runtime(components)


def cli_entrypoint() -> None:
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
        config_file = pathlib.Path(get_package_directory()) / "config" / "log_config.json"

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

    app_entrypoint(args)


# Note: start_message_bus_loop and message_bus_main_loop functions have been
# replaced by the DistributedStartupCoordinator class in woodwork.core.distributed_startup
# The new implementation provides proper event loop ownership and clean shutdown
