import argparse
from collections.abc import Sequence

from .errors import ParseError


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """
    Parse command line arguments to configure Woodwork.

    Args:
        args (Optional[Sequence[str]], optional): Optional . Defaults to None.

    Returns:
        argparse.Namespace: The parsed command line arguments as a Namespace object.
    """

    parser = argparse.ArgumentParser(
        description="Woodwork CLI for managing and executing workflows.",
        add_help=True,
    )

    # TODO: @willwoodward - Remove debug when appropriate in your release cycle.
    # Currently defaults to run if debug is chosen.
    parser.add_argument(
        "--mode",
        choices=["run", "debug", "embed", "clear"],
        default="run",
        help="Set the mode of operation for the CLI. Use 'debug' for debugging purposes. (default: run)",
    )

    parser.add_argument(
        "--init",
        type=str,
        nargs="?",
        choices=["none", "isolated", "all"],
        const="none",
        default=None,
        help=(
            "Initialize Woodwork with options. Use 'isolated' to create an isolated environment,"
            "'all' to initialize all components. Default is none when no argument is provided. "
            "If no argument is provided, initialisation will not be carried out. "
        ),
    )

    parser.add_argument(
        "--workflow",
        choices=["none", "add", "remove", "find"],
        default="none",
        help=(
            "Manage workflows. Use 'add' to add a workflow, 'remove' to remove a workflow, "
            "'find' to search for a workflow. (default: none)"
        ),
    )

    parser.add_argument(
        "--target",
        default="",
        metavar="[File path/Search query/Workflow ID]",
        help=(
            "For adding workflows, provide the file path to the workflow. "
            + "For finding workflows, provide a search query. "
            + "For removing workflows, provide the workflow ID. (default: empty string)"
        ),
    )

    parser.add_argument(
        "--logConfig",
        default=None,
        help=("A custom path to a JSON logging configuration file."),
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Display the version of Woodwork and exit.",
    )

    return parser.parse_args(args)


def check_parse_conflicts(args: argparse.Namespace) -> None:
    """
    Check for conflicts in the parsed arguments.

    Args:
        args (argparse.Namespace): The parsed command line arguments.

    Raises:
        ParseError: If there are conflicts in the arguments.
    """

    if args.workflow != "none" and args.target == "":
        raise ParseError(
            message="Target argument is required for workflow operations. See --help for more information.",
        )
