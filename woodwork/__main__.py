from woodwork.dependencies import init, activate_virtual_environment, init_all
from woodwork.helper_functions import set_globals
from woodwork.errors import WoodworkException

import sys


def custom_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, WoodworkException):
        print(f"{exc_value}")
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main():
    sys.excepthook = custom_excepthook

    # woodwork
    if len(sys.argv) == 1:
        activate_virtual_environment()

        from woodwork.config_parser import main_function

        main_function()

    # woodwork --debug
    elif sys.argv[1] == "--debug":
        set_globals(mode="debug")
        activate_virtual_environment()

        from woodwork.config_parser import main_function

        main_function()

    # woodwork init
    elif sys.argv[1] == "init":
        if len(sys.argv) == 2:
            init()
        else:
            if sys.argv[2] == "--isolated":
                init({"isolated": True})
            if sys.argv[2] == "--all":
                init_all({"isolated": True})

    # woodwork embed
    elif sys.argv[1] == "embed":
        set_globals(inputs_activated=False, mode="embed")
        activate_virtual_environment()
        from woodwork.config_parser import main_function, embed_all

        main_function()
        embed_all()

    # woodwork clear
    elif sys.argv[1] == "clear":
        set_globals(inputs_activated=False, mode="clear")
        activate_virtual_environment()
        from woodwork.config_parser import main_function, clear_all

        main_function()
        clear_all()

    # woodwork add
    elif sys.argv[1] == "add":
        # woodwork add workflow
        if sys.argv[2] == "workflow":
            file_path = sys.argv[3]
            set_globals(inputs_activated=False)
            activate_virtual_environment()
            from woodwork.config_parser import main_function, add_action_plan

            main_function()
            add_action_plan(file_path)
