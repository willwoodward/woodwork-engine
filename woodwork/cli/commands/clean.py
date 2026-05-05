"""Clean command - tear down containers and remove .woodwork/ directory."""

import click


@click.command("clean")
@click.confirmation_option(prompt="This will remove .woodwork/ and Docker resources. Continue?")
def clean_cmd():
    """Tear down containers and remove .woodwork/ directory."""
    from woodwork.cli.cleanup import clean_all

    clean_all()
    click.echo("Cleanup complete.")
