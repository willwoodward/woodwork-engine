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
from .progress.lifecycles import init_component, parallel_init_component, start_component, parallel_start_component

from . import globals

log = logging.getLogger(__name__)

def app_entrypoint(args):
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

        components = config_parser.task_m._tools
        parallel_func_apply(components, parallel_init_component, init_component, "initialized", "initializing")
        generate_exported_objects_file(registry=registry)
        return

    if args.gui is not None:
        if args.gui == "run":
            log.debug("GUI is set to run.")
            dependencies.activate_virtual_environment()
            config_parser.main_function()
            from woodwork.gui.gui import GUI

            gui = GUI(config_parser.task_m)
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

    deployer = Deployer()
    deployer.main()

    # Start all components that implement the Startable interface
    components = config_parser.task_m._tools
    parallel_func_apply(components, parallel_start_component, start_component, "started", "starting")

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

    app_entrypoint(args)
