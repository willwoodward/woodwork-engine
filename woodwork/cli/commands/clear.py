"""Clear command - wipe knowledge base data."""

import click


@click.command("clear")
@click.argument("component", required=False)
@click.confirmation_option(prompt="This will wipe knowledge base data. Continue?")
def clear_cmd(component):
    """Wipe knowledge base data."""
    from woodwork.cli.main import (
        parse_and_validate_config,
        deploy_containers,
        start_components,
    )
    from woodwork.cli.setup_defaults import copy_prompts
    from woodwork.config import config_parser

    copy_prompts()
    components = parse_and_validate_config()
    deploy_containers()
    start_components(components)
    config_parser.clear_all()
    click.echo("Knowledge base data cleared.")
