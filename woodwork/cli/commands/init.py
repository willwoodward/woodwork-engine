"""Init command - install component dependencies."""

import click


@click.command("init")
@click.option("--isolated", is_flag=True, help="Create isolated venv without system site-packages.")
@click.option("--all", "install_all", is_flag=True, help="Install all optional component dependencies.")
def init_cmd(isolated, install_all):
    """Install component dependencies for .ww config files."""
    from woodwork.config import dependencies

    options = {
        "isolated": isolated or install_all,
        "all": install_all,
    }
    dependencies.init(options)
