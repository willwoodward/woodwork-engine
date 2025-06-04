## dev-main.py acts as the developer entrypoint for the Woodwork library. Primarily, this configures a development
# logging setup and runs the main function of the Woodwork library. You can run this script directly to start,
# as well as pass in command line arguments to control the behavior of the Woodwork library. For information on
# arguments, use `[python3/uv run/etc.] dev-main.py --help`.

import logging

from woodwork import __main__ as m


import json
import logging.config
import pathlib


def create_custom_logger(config_path: str) -> None:
    config_file = pathlib.Path(config_path)

    with open(config_file) as f_in:
        config = json.load(f_in)

    # Get the directory for logging as specified in the logging_config.json file to
    # create the log directory if it does not exist. The filename in the config file
    # must be only one folder deep from the root, such as "./logs/", however the
    # directory name can be anything.
    log_directory = pathlib.Path(config["handlers"]["file"]["filename"].split("/")[0])
    if not log_directory.exists():
        log_directory.mkdir()

    logging.config.dictConfig(config)
    # queue_handler = logging.getHandlerByName("queue_handler")
    # if queue_handler is not None:
    #    queue_handler.handle.listener.start()
    #    atexit.register(queue_handler.handle.listener.stop)

    return None


if __name__ == "__main__":
    create_custom_logger("./config/log_config.json")
    m.main()
