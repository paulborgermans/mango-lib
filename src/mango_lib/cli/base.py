""" ManGO command line interface.

    Base CLI for the ManGO ecosystem. Other packages (e.g. mango_portal,
    mango_flow) can register their own subcommands via the
    ``mango.cli.plugins`` entry point group.

    This is defined via the pyproject.toml config, for example
    ```toml
    [project.entry-points."mango.cli.plugins"]
    mango_portal = "mango_portal.cli:register"
    mango_flow = "mango_flow.cli:register"
    ```
"""
from importlib.metadata import entry_points

import click


@click.group()
@click.version_option()
@click.pass_context
def mango(ctx: click.Context) -> None:
    """ManGO command line interface.

    Base CLI for the ManGO ecosystem. Other packages (e.g. mango_portal,
    mango_flow) can register their own subcommands via the
    ``mango.cli.plugins`` entry point group.
    """
    ctx.ensure_object(dict)


def _load_plugins() -> None:
    """Discover and load CLI plugins from installed packages.
    
    See also https://setuptools.pypa.io/en/latest/userguide/entry_point.html 
    for more information on entry points. Especially the section Entry Points for Plugins. 
    """
    for ep in entry_points(group="mango.cli.plugins"):
        try:
            plugin = ep.load()
            if callable(plugin):
                plugin() # Call the plugin register() function to register its commands
        except Exception as exc:  # noqa: BLE001
            click.echo(f"Failed to load plugin {ep.name}: {exc}", err=True)


_load_plugins()
