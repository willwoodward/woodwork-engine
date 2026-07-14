"""Run command - parse, deploy, start, and run the application."""

import click


@click.command("run")
@click.option("--config", "-c", default="main.ww", help="Path to .ww config file.")
@click.option("--gui", type=click.Choice(["fastapi"]), default=None, help="Launch GUI mode.")
@click.pass_context
def run_cmd(ctx, config, gui):
    """Parse, deploy, start, and run the application (default)."""
    from woodwork.cli.main import (
        parse_and_validate_config,
        generate_exports,
        deploy_containers,
        start_components,
        start_runtime,
    )
    from woodwork.cli.setup_defaults import copy_prompts

    copy_prompts()

    if gui == "fastapi":
        import asyncio

        from woodwork.config import dependencies

        dependencies.activate_virtual_environment()
        from woodwork.gui.fastapi_gui_server import start_gui_server

        asyncio.run(start_gui_server())
        return

    components = parse_and_validate_config()
    generate_exports()
    deploy_containers()
    start_components(components)
    start_runtime(components)
