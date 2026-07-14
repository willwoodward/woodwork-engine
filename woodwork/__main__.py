"""Entry point for `python -m woodwork`."""

from woodwork.cli.app import cli

# Keep legacy entry point for backward compatibility
from woodwork.cli.main import app_entrypoint, cli_entrypoint  # noqa: F401


def run_as_standalone_app() -> None:
    """Legacy entry point — delegates to click CLI."""
    cli()


if __name__ == "__main__":
    cli()
