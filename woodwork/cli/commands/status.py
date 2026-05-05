"""Status command - show running components and health."""

import os

import click


@click.command("status")
def status_cmd():
    """Show running components, deployment mode, and health."""
    woodwork_dir = os.path.join(os.getcwd(), ".woodwork")

    if os.path.exists(woodwork_dir):
        click.echo("Woodwork environment: initialized")
        venv_path = os.path.join(woodwork_dir, "env")
        if os.path.exists(venv_path):
            click.echo(f"  Virtual env: {venv_path}")
    else:
        click.echo("Woodwork environment: not initialized")
        click.echo("  Run 'woodwork init' to set up.")
        return

    # Check for Docker containers
    try:
        import docker

        client = docker.from_env()
        containers = [c for c in client.containers.list() if "woodwork" in c.name.lower()]
        if containers:
            click.echo(f"\nRunning containers ({len(containers)}):")
            for c in containers:
                click.echo(f"  {c.name}: {c.status}")
        else:
            click.echo("\nNo running woodwork containers.")
    except Exception:
        click.echo("\nDocker: not available")
