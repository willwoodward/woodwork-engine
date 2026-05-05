"""Woodwork CLI application using click subcommands."""

import json
import logging
import logging.config
import pathlib
import sys

import click

from woodwork.utils import get_package_directory
from woodwork.utils.errors import WoodworkError


def _setup_logging(log_config=None, verbose=False):
    """Configure logging from config file."""
    if log_config:
        config_file = pathlib.Path(log_config)
    else:
        config_file = pathlib.Path(get_package_directory()) / "config" / "log_config.json"

    try:
        with pathlib.Path.open(config_file) as f_in:
            config = json.load(f_in)
    except FileNotFoundError:
        logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
        return

    log_directory = pathlib.Path(config["handlers"]["file"]["filename"].split("/")[0])
    if not log_directory.exists():
        log_directory.mkdir()

    if verbose:
        config["root"]["level"] = "DEBUG"

    logging.config.dictConfig(config)


def _custom_excepthook(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, WoodworkError):
        click.echo(f"{exc_value}", err=True)
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Display version and exit.")
@click.option("--log-config", type=click.Path(exists=True), help="Custom JSON logging config file.")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose (DEBUG) logging.")
@click.pass_context
def cli(ctx, version, log_config, verbose):
    """Woodwork - Declarative AI Agent Composition."""
    sys.excepthook = _custom_excepthook
    ctx.ensure_object(dict)
    ctx.obj["log_config"] = log_config
    ctx.obj["verbose"] = verbose

    _setup_logging(log_config, verbose)

    if version:
        from woodwork.utils.helper_functions import get_version_from_pyproject

        toml_path = str(pathlib.Path(__file__).parent.parent.parent / "pyproject.toml")
        click.echo(f"Woodwork version: {get_version_from_pyproject(toml_path)}")
        ctx.exit(0)

    # Default to 'run' if no subcommand given
    if ctx.invoked_subcommand is None:
        ctx.invoke(run_cmd)


# Import and register subcommands
from woodwork.cli.commands.run import run_cmd  # noqa: E402
from woodwork.cli.commands.init import init_cmd  # noqa: E402
from woodwork.cli.commands.build import build_cmd  # noqa: E402
from woodwork.cli.commands.deploy import deploy_cmd  # noqa: E402
from woodwork.cli.commands.dev import dev_cmd  # noqa: E402
from woodwork.cli.commands.clean import clean_cmd  # noqa: E402
from woodwork.cli.commands.status import status_cmd  # noqa: E402
from woodwork.cli.commands.embed import embed_cmd  # noqa: E402
from woodwork.cli.commands.clear import clear_cmd  # noqa: E402
from woodwork.cli.commands.workflow import workflow_group  # noqa: E402

cli.add_command(run_cmd)
cli.add_command(init_cmd)
cli.add_command(build_cmd)
cli.add_command(deploy_cmd)
cli.add_command(dev_cmd)
cli.add_command(clean_cmd)
cli.add_command(status_cmd)
cli.add_command(embed_cmd)
cli.add_command(clear_cmd)
cli.add_command(workflow_group)
