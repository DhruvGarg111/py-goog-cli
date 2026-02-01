"""Configuration CLI commands."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from pygog.config import get_config

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command("path")
def path_cmd():
    """Show configuration file path."""
    config = get_config()
    console.print(str(config.path))


@app.command("list")
def list_cmd():
    """List all configuration values."""
    config = get_config()
    data = config.get_all()

    if not data:
        console.print("[yellow]No configuration set.[/yellow]")
        return

    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    for key, value in sorted(data.items()):
        table.add_row(key, str(value))

    console.print(table)


@app.command("keys")
def keys_cmd():
    """List all configuration keys."""
    config = get_config()
    keys = config.keys()

    if not keys:
        console.print("[yellow]No configuration set.[/yellow]")
        return

    for key in sorted(keys):
        console.print(key)


@app.command("get")
def get_cmd(
    key: str = typer.Argument(..., help="Configuration key"),
):
    """Get a configuration value."""
    config = get_config()
    value = config.get(key)

    if value is None:
        console.print(f"[yellow]Key '{key}' not set[/yellow]")
    else:
        console.print(str(value))


@app.command("set")
def set_cmd(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """Set a configuration value."""
    config = get_config()

    import json
    try:
        parsed = json.loads(value)
        config.set(key, parsed)
    except json.JSONDecodeError:
        config.set(key, value)

    console.print(f"[green][OK][/green] Set {key} = {value}")


@app.command("unset")
def unset_cmd(
    key: str = typer.Argument(..., help="Configuration key to remove"),
):
    """Remove a configuration value."""
    config = get_config()

    if config.unset(key):
        console.print(f"[green][OK][/green] Removed '{key}'")
    else:
        console.print(f"[yellow]Key '{key}' not found[/yellow]")
