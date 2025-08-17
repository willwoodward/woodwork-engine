import logging
import sys

from woodwork.cli.main import app_entrypoint, cli_entrypoint
from woodwork.utils.errors import WoodworkError

log = logging.getLogger(__name__)


def custom_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, WoodworkError):
        print(f"{exc_value}")
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def main(args) -> None:
    sys.excepthook = custom_excepthook
    app_entrypoint(args)


def run_as_standalone_app() -> None:
    cli_entrypoint()
