"""Workflow command group - manage cached workflows."""

import click


@click.group("workflow")
def workflow_group():
    """Manage cached workflows."""
    pass


@workflow_group.command("list")
def workflow_list():
    """List all cached workflows."""
    click.echo("Workflow listing not yet implemented.")


@workflow_group.command("remove")
@click.argument("workflow_id")
def workflow_remove(workflow_id):
    """Remove a cached workflow by ID."""
    from woodwork.cli.main import parse_and_validate_config
    from woodwork.cli.setup_defaults import copy_prompts
    from woodwork.config import config_parser

    copy_prompts()
    parse_and_validate_config()
    config_parser.delete_action_plan(workflow_id)
    click.echo(f"Workflow {workflow_id} removed.")


@workflow_group.command("find")
@click.argument("query")
def workflow_find(query):
    """Find workflows matching a query."""
    from woodwork.cli.main import parse_and_validate_config
    from woodwork.cli.setup_defaults import copy_prompts
    from woodwork.config import config_parser

    copy_prompts()
    parse_and_validate_config()
    config_parser.find_action_plan(query)
