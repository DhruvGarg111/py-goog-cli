"""Main CLI application for pygog."""

from __future__ import annotations

from typing import Literal, cast

import typer
from rich.console import Console
from typer.core import TyperGroup

from pygog import __version__
from pygog.commands import ask, auth, calendar, config_cmd, drive, gmail, tasks, time_cmd
from pygog.config import get_config
from pygog.context import CliContext, bind_context, get_context, state
from pygog.errors import PygogError, ValidationError, emit_error


class ErrorBoundaryGroup(TyperGroup):
    """Click group that converts typed application errors at the CLI edge."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except (KeyboardInterrupt, SystemExit):
            raise
        except PygogError as error:
            context = get_context(ctx)
            emit_error(
                error,
                json_output=context.json_output,
                verbose=context.verbose,
            )
            raise typer.Exit(error.exit_code)


app = typer.Typer(
    name="pygog",
    help="pygog - Google in your terminal.\n\nFast, script-friendly CLI for Gmail, Calendar, Drive, Tasks, and more.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    cls=ErrorBoundaryGroup,
)

console = Console()
err_console = Console(stderr=True)

# Compatibility export: callers importing ``pygog.cli.State`` or
# ``pygog.cli.state`` continue to receive the typed context object.
State = CliContext


def _configure_consoles(color: str) -> None:
    """Configure Rich through its public constructor options."""
    global console, err_console

    if color == "never":
        console = Console(force_terminal=False, no_color=True)
        err_console = Console(stderr=True, force_terminal=False, no_color=True)
    elif color == "always":
        console = Console(force_terminal=True, no_color=False)
        err_console = Console(stderr=True, force_terminal=True, no_color=False)
    else:
        console = Console(force_terminal=None, no_color=None)
        err_console = Console(stderr=True, force_terminal=None, no_color=None)


def version_callback(value: bool):
    if value:
        console.print(f"pygog version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    account: str | None = typer.Option(
        None,
        "--account",
        "-a",
        help="Account email or alias to use",
        envvar="GOG_ACCOUNT",
    ),
    client: str | None = typer.Option(
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
    color: str | None = typer.Option(
        None,
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
    config = get_config()
    context = bind_context(typer_context(), state)

    selected_color = color if color is not None else config.color_mode
    if selected_color not in {"auto", "always", "never"}:
        raise ValidationError(
            f"Invalid color mode '{selected_color}'. Choose auto, always, or never."
        )

    context.account = config.resolve_account(account)
    context.client = client
    context.json_output = bool(json_output or config.json_output)
    context.plain_output = bool(plain_output or config.plain_output)
    context.color = cast(Literal["auto", "always", "never"], selected_color)
    context.verbose = verbose
    context.force = force
    context.no_input = no_input

    if context.json_output and context.plain_output:
        raise ValidationError("--json and --plain are mutually exclusive")

    _configure_consoles(selected_color)


app.add_typer(auth.app, name="auth", help="Manage authentication and accounts")
app.add_typer(config_cmd.app, name="config", help="Manage configuration")
app.add_typer(time_cmd.app, name="time", help="Display time information")

app.add_typer(gmail.app, name="gmail", help="Gmail operations")
app.add_typer(calendar.app, name="calendar", help="Calendar operations")
app.add_typer(drive.app, name="drive", help="Drive operations")
app.add_typer(tasks.app, name="tasks", help="Tasks operations")

app.add_typer(ask.app, name="ask", help="Ask using natural language")


def typer_context():
    """Return the current Click context without requiring Typer injection.

    Typer versions in the supported range differ in how they recognise a
    callback parameter annotated as ``typer.Context``.  Looking up Click's
    current context keeps direct Python calls backward-compatible while still
    populating ``Context.obj`` for real CLI invocations.
    """
    from typer.main import get_current_context

    return get_current_context(silent=True)
