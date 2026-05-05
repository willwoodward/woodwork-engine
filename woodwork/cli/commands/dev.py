"""Dev command - run with verbose logging."""

import logging

import click


@click.command("dev")
@click.option("--config", "-c", default="main.ww", help="Path to .ww config file.")
def dev_cmd(config):
    """Run with verbose logging for development."""
    # Force verbose logging
    logging.getLogger().setLevel(logging.DEBUG)

    from woodwork.cli.main import (
        parse_and_validate_config,
        generate_exports,
        deploy_containers,
        start_components,
        start_runtime,
    )
    from woodwork.cli.setup_defaults import copy_prompts

    copy_prompts()
    components = parse_and_validate_config()
    generate_exports()
    deploy_containers()
    start_components(components)
    start_runtime(components)
