"""Typed state shared by the CLI and its command callbacks.

The command modules still import ``pygog.cli.state`` for compatibility.  New
code can use :func:`get_context` and :func:`bind_context` to migrate to the
Click/Typer context object without requiring a flag-day rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from typer.main import get_current_context

if TYPE_CHECKING:
    from pygog.config import Config

ColorMode = Literal["auto", "always", "never"]


@dataclass
class CliContext:
    """Runtime options resolved for one CLI invocation."""

    account: str | None = None
    client: str | None = None
    json_output: bool = False
    plain_output: bool = False
    color: ColorMode = "auto"
    verbose: bool = False
    force: bool = False
    no_input: bool = False

    @property
    def config(self) -> Config:
        """Return the lazily-loaded application configuration."""
        from pygog.config import get_config

        return get_config()


# Compatibility names for code written against the pre-context CLI.
State = CliContext
state = CliContext()


def get_context(ctx: Any | None = None) -> CliContext:
    """Return the typed context associated with *ctx*.

    When called from a Typer callback, the current Click context is discovered
    automatically.  If no context exists (for example, a legacy unit test
    calls a command function directly), the compatibility singleton is
    returned.
    """
    if ctx is None:
        ctx = get_current_context(silent=True)

    if ctx is None:
        return state

    if isinstance(ctx.obj, CliContext):
        return ctx.obj

    # Existing callers may have populated ``obj`` with another value.  Keep
    # that value untouched only when it is useful to the caller; CLI state is
    # always represented by our typed object.
    ctx.obj = state
    return state


def bind_context(ctx: Any | None, value: CliContext | None = None) -> CliContext:
    """Attach and return a typed CLI context through ``click.Context.obj``."""
    context = value or (get_context(ctx) if ctx is not None else state)
    if ctx is not None:
        ctx.obj = context
    return context


# More explicit spelling for new call sites.
get_cli_context = get_context
bind_cli_context = bind_context


__all__ = [
    "ColorMode",
    "CliContext",
    "State",
    "state",
    "get_context",
    "get_cli_context",
    "bind_context",
    "bind_cli_context",
]
