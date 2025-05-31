import logging
import sys

import woodwork.config_parser as config_parser
import woodwork.dependencies as dependencies
from woodwork.errors import WoodworkException
from woodwork.helper_functions import set_globals


def custom_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, WoodworkException):
        print(f"{exc_value}")
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main() -> None:
    sys.excepthook = custom_excepthook

    # TODO: Improve this logging logic, kinda self-dependent...but works
    try:
        args = config_parser.parse_args()
        logging.basicConfig(level=args.log.upper())
        # TODO: Create a custom logger that extends the root logger
        # Set a delineator for a new application run in log file
        logging.debug("\n" + "=" * 60 + " NEW LOG RUN " + "=" * 60 + "\n")
    except config_parser.ParseError as e:
        logging.basicConfig(level=logging.INFO)
        # Set a delineator for a new application run in log file
        logging.debug("\n" + "=" * 60 + " NEW LOG RUN " + "=" * 60 + "\n")
        logging.critical("ParseError: %s", e)
        return



    logging.debug(f"Arguments: {args}")

    if args.workflow != "none" and args.target == "":
        logging.critical("Workflow: %s - Target argument is required for workflow operations.")
        raise ValueError("Target argument is required for workflow operations.")

    # Set globals based on flags before execution
    match args.mode:
        case "run":
            set_globals(mode="run", inputs_activated=True)
        case "debug":
            set_globals(mode="debug", inputs_activated=True)
        case "embed":
            set_globals(mode="embed", inputs_activated=False)
        case "clear":
            set_globals(mode="clear", inputs_activated=False)
        case _:
            # ArgParse will SysExit if choice not in list
            pass

    if args.init != "none":
        options = {}
        if args.init == "isolated":
            options["isolated"] = True
        elif args.init == "all":
            options["isolated"] = True
            options["all"] = True
        dependencies.init(options)
    else:
        dependencies.init()

    if args.workflow != "none":
        if args.mode in ["run", "debug"]:
            logging.warning(
                "Possible conflict: Mode is %s which conflicts with %s Workflow.", args.mode, args.workflow
            )  # TODO: @willwoodward Make more specific regarding what `inputs_activated` means
        set_globals(inputs_activated=False)

    # Execute the main functionality
    dependencies.activate_virtual_environment()

    config_parser.main_function()

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
        case "remove":
            config_parser.delete_action_plan(args.target)
        case "find":
            config_parser.find_action_plan(args.target)
        case _:
            # ArgParse will SysExit if choice not in list
            pass

    return
