"""Deploy command - build and start containers."""

import click


@click.command("deploy")
@click.option("--config", "-c", default="main.ww", help="Path to .ww config file.")
def deploy_cmd(config):
    """Build and start containers (local or remote)."""
    from woodwork.cli.main import (
        parse_and_validate_config,
        generate_exports,
        deploy_containers,
        start_components,
    )
    from woodwork.cli.setup_defaults import copy_prompts

    copy_prompts()
    components = parse_and_validate_config()
    generate_exports()
    deploy_containers()
    start_components(components)
    click.echo("Deployment complete. Components are running.")
