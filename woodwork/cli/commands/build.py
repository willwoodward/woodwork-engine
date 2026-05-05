"""Build command - parse .ww and generate deployment artifacts without running."""

import click


@click.command("build")
@click.option("--config", "-c", default="main.ww", help="Path to .ww config file.")
def build_cmd(config):
    """Parse .ww file and generate deployment artifacts without running."""
    from woodwork.cli.main import parse_and_validate_config, generate_exports
    from woodwork.cli.setup_defaults import copy_prompts

    copy_prompts()
    parse_and_validate_config()
    generate_exports()
    click.echo("Build complete.")
