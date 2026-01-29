"""Main CLI application for pygog."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from pygog import __version__
from pygog.config import get_config

# Create main app
app = typer.Typer(
    name="pygog",
    help="pygog - Google in your terminal.\n\nFast, script-friendly CLI for Gmail, Calendar, Drive, Tasks, and more.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Console for output
console = Console()
err_console = Console(stderr=True)


# Global state
class State:
    """Global CLI state."""

    def __init__(self):
        self.account: str | None = None
        self.client: str = "default"
        self.json_output: bool = False
        self.plain_output: bool = False
        self.color: str = "auto"
        self.verbose: bool = False
        self.force: bool = False
        self.no_input: bool = False

    @property
    def config(self):
        return get_config()


state = State()


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        console.print(f"pygog version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    account: Optional[str] = typer.Option(
        None,
        "--account",
        "-a",
        help="Account email or alias to use",
        envvar="GOG_ACCOUNT",
    ),
    client: Optional[str] = typer.Option(
        None,
        "--client",
        help="OAuth client name",
        envvar="GOG_CLIENT",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON to stdout",
        envvar="GOG_JSON",
    ),
    plain_output: bool = typer.Option(
        False,
        "--plain",
        help="Output plain TSV to stdout",
        envvar="GOG_PLAIN",
    ),
    color: str = typer.Option(
        "auto",
        "--color",
        help="Color mode: auto, always, never",
        envvar="GOG_COLOR",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmations for destructive commands",
    ),
    no_input: bool = typer.Option(
        False,
        "--no-input",
        help="Never prompt; fail instead",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """Global options callback."""
    config = get_config()
    
    # Set state from args, falling back to config/env
    state.account = config.resolve_account(account)
    state.client = client or config.client
    state.json_output = json_output or config.json_output
    state.plain_output = plain_output or config.plain_output
    state.color = color
    state.verbose = verbose
    state.force = force
    state.no_input = no_input
    
    # Configure console based on color mode
    if color == "never":
        console._force_terminal = False
        err_console._force_terminal = False
    elif color == "always":
        console._force_terminal = True
        err_console._force_terminal = True


# Import and register command groups
from pygog.commands import auth, config_cmd, time_cmd

app.add_typer(auth.app, name="auth", help="Manage authentication and accounts")
app.add_typer(config_cmd.app, name="config", help="Manage configuration")
app.add_typer(time_cmd.app, name="time", help="Display time information")

# Import service commands (will be added as they're implemented)
from pygog.commands import gmail, calendar, drive, tasks

app.add_typer(gmail.app, name="gmail", help="Gmail operations")
app.add_typer(calendar.app, name="calendar", help="Calendar operations")
app.add_typer(drive.app, name="drive", help="Drive operations")
app.add_typer(tasks.app, name="tasks", help="Tasks operations")

# Agent command
from pygog.commands import ask
app.add_typer(ask.app, name="ask", help="Ask using natural language")

