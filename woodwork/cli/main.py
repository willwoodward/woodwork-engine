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
from woodwork.cli.setup_defaults import copy_prompts
from woodwork.cli.cleanup import clean_all
from woodwork.utils import get_package_directory

import woodwork.globals as globals

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

    if getattr(args, "clean", False):
        log.info("--clean flag provided: running cleanup and exiting.")
        clean_all()
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

    copy_prompts()

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
    
    # Debug: Show which orchestration mode is active
    if globals.global_config.get("message_bus_active", False):
        log.info("🚀 Woodwork running with DISTRIBUTED MESSAGE BUS orchestration")
    else:
        log.info("🔧 Woodwork running with TASK MASTER orchestration")

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
            pass
        case "remove":
            config_parser.delete_action_plan(args.target)
            log.debug("%s Workflow removed with id: %s.", args.workflow, args.target)
        case "find":
            config_parser.find_action_plan(args.target)
            log.debug("%s Workflow found with query: %s.", args.workflow, args.target)
        case _:
            # ArgParse will SysExit if choice not in list
            pass

    # Only start Task Master if message bus is not active
    if not globals.global_config.get("message_bus_active", False):
        config_parser.task_m.start()
        log.info("Task Master started (message bus not active)")
    else:
        log.info("Skipping Task Master start - message bus is handling component orchestration")
        # Start message bus main loop instead
        start_message_bus_loop(config_parser.task_m._tools)


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


def start_message_bus_loop(tools):
    """Start the message bus main loop to handle input/output cycling"""
    import asyncio
    import threading
    from woodwork.components.inputs.inputs import inputs
    from woodwork.components.outputs.outputs import outputs
    from woodwork.deployments.router import get_router

    log.info("🚀 Starting message bus main loop...")

    # Find input components
    input_components = [tool for tool in tools if isinstance(tool, inputs)]

    if not input_components:
        log.error("No input components found - cannot start message bus loop")
        return

    input_component = input_components[0]  # Use first input component
    log.info("Using input component: %s", input_component.name)

    # Start message bus in background thread to ensure async tasks run properly
    def run_message_bus_background():
        """Background thread to run the message bus with proper async event loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def setup_and_run():
            try:
                # Start the message bus properly with async tasks in this event loop
                from woodwork.core.message_bus.factory import get_global_message_bus
                message_bus = await get_global_message_bus()
                log.info("Message bus started with background tasks (retry processor, cleanup)")

                # Also ensure the integration manager is properly set up
                from woodwork.core.message_bus.integration import get_global_message_bus_manager
                manager = get_global_message_bus_manager()

                # Set up streaming like Task Master does
                router = get_router()
                stream_manager = await router.setup_streaming()
                if stream_manager:
                    log.debug("Message bus: Streaming set up successfully")
                else:
                    log.warning("Message bus: Failed to set up streaming")

                # Start the main input/output loop
                await message_bus_main_loop(input_component)

            except Exception as e:
                log.error("Error in message bus main loop: %s", e)
                import traceback
                traceback.print_exc()
            finally:
                # Clean shutdown
                try:
                    message_bus = await get_global_message_bus()
                    if hasattr(message_bus, 'stop'):
                        await message_bus.stop()
                        log.info("Message bus stopped cleanly")
                except Exception as e:
                    log.error("Error stopping message bus: %s", e)

        try:
            loop.run_until_complete(setup_and_run())
        finally:
            loop.close()

    # Start the background thread
    message_bus_thread = threading.Thread(target=run_message_bus_background, daemon=True)
    message_bus_thread.start()

    # Wait for the thread to complete (this keeps main thread alive)
    try:
        message_bus_thread.join()
    except KeyboardInterrupt:
        log.info("Keyboard interrupt - shutting down message bus loop")
    except Exception as e:
        log.error("Error in message bus thread: %s", e)
        import traceback
        traceback.print_exc()


async def message_bus_main_loop(input_component):
    """Main message bus input/output loop (replaces Task Master loop)"""
    
    log.info("🔄 Message bus main loop started - waiting for input...")
    
    while True:
        try:
            # Get input from the input component (like Task Master does)
            x = input_component.input_function()
            
            # Handle exit conditions
            if x == "exit" or x == ";":
                log.info("Exit command received - shutting down message bus loop")
                break
            
            # Instead of Task Master's linked list traversal, emit through message bus
            log.debug("Processing input through message bus: %s", str(x)[:100])
            
            # Create proper InputReceivedPayload for the event system
            from woodwork.types import InputReceivedPayload
            payload = InputReceivedPayload(
                input=x,
                inputs={},
                session_id=getattr(input_component, 'session_id', 'default'),
                component_id=input_component.name,
                component_type="inputs"
            )
            
            # Emit the input event - the message bus will handle routing automatically
            await input_component.emit("input_received", payload)
            
            log.debug("Input processed and routed through message bus")
            
        except KeyboardInterrupt:
            log.info("Keyboard interrupt - shutting down message bus loop")
            break
        except Exception as e:
            log.error("Error in message bus main loop: %s", e)
            # Continue the loop even on errors
            continue
    
    # Clean up
    log.info("Message bus main loop shutting down...")
    
    # Close all components like Task Master does
    from woodwork.parser.config_parser import task_m
    task_m.close_all()
