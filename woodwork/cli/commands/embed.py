"""Embed command - trigger embedding on knowledge bases."""

import click


@click.command("embed")
@click.argument("component", required=False)
def embed_cmd(component):
    """Trigger embedding on knowledge base components."""
    from woodwork.cli.main import (
        parse_and_validate_config,
        deploy_containers,
        start_components,
    )
    from woodwork.cli.setup_defaults import copy_prompts
    from woodwork.parser import config_parser

    copy_prompts()
    components = parse_and_validate_config()
    deploy_containers()
    start_components(components)
    config_parser.embed_all()
    click.echo("Embedding complete.")
