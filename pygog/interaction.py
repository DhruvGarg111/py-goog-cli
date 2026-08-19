"""Shared interaction policy for command mutations.

Commands call this module before constructing a service.  Keeping the policy at
that boundary makes ``--force``, ``--no-input``, and machine-readable errors
behave consistently across Google services.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NoReturn, TypeVar

import typer
from rich.console import Console

from pygog.output import print_json, print_plain

T = TypeVar("T")


@dataclass(frozen=True)
class InteractionPolicy:
    """Authorize one potentially destructive command action.

    ``force`` and ``no_input`` are copied from the CLI state by
    :func:`confirm_destructive`.  The class is deliberately state-free so it
    can also be tested and used by commands without importing the CLI module.
    """

    force: bool = False
    no_input: bool = False
    json_output: bool = False
    plain_output: bool = False

    def authorize(
        self,
        action: str,
        preview: str,
        *,
        local_force: bool = False,
        dry_run: bool = False,
    ) -> bool:
        """Return whether a mutation may execute, or exit safely.

        A dry-run is already safe and therefore returns ``False`` to tell the
        caller not to invoke its service method.  A declined interactive
        confirmation exits with status zero, preserving the CLI's historical
        cancellation behavior.  Missing confirmation in automation is an
        error (status one).
        """
        if dry_run:
            return False
        if local_force or self.force:
            return True

        message = (
            f"Confirmation required for {action}. "
            "Re-run with --force or --dry-run, or omit --no-input to confirm interactively."
        )
        if self.no_input:
            fail_interaction(
                message,
                code="confirmation_required",
                json_output=self.json_output,
                plain_output=self.plain_output,
            )

        # A prompt would corrupt machine-readable stdout.  Automation should
        # use --force explicitly, just as it must when --no-input is set.
        if self.json_output or self.plain_output:
            fail_interaction(
                message,
                code="confirmation_required",
                json_output=self.json_output,
                plain_output=self.plain_output,
            )

        if typer.confirm(f"{action}: {preview}\nProceed?"):
            return True
        raise typer.Exit(0)


def _cli_state() -> Any:
    """Load CLI state lazily to avoid the command/CLI import cycle."""
    from pygog.cli import state

    return state


def confirm_destructive(
    action: str,
    preview: str,
    *,
    local_force: bool = False,
    dry_run: bool = False,
) -> bool:
    """Apply the shared policy using global CLI flags."""
    state = _cli_state()
    return InteractionPolicy(
        force=bool(state.force),
        no_input=bool(state.no_input),
        json_output=bool(state.json_output),
        plain_output=bool(state.plain_output),
    ).authorize(
        action,
        preview,
        local_force=local_force,
        dry_run=dry_run,
    )


def fail_interaction(
    message: str,
    *,
    code: str = "error",
    json_output: bool | None = None,
    plain_output: bool | None = None,
) -> NoReturn:
    """Emit a clean error response and exit nonzero.

    JSON errors are the only content written to stdout.  Plain-output and
    human diagnostics are written to stderr so shell pipelines never receive
    a mixed response.
    """
    if json_output is None or plain_output is None:
        state = _cli_state()
        if json_output is None:
            json_output = bool(state.json_output)
        if plain_output is None:
            plain_output = bool(state.plain_output)

    if json_output:
        print_json({"error": {"code": code, "message": message}})
    else:
        sys.stderr.write(f"Error: {message}\n")
    raise typer.Exit(1)


def execute_mutation(
    operation: Callable[[], T],
    *,
    action: str,
    json_output: bool | None = None,
    plain_output: bool | None = None,
) -> T:
    """Run an authorized mutation and serialize operational failures safely."""
    try:
        return operation()
    except typer.Exit:
        raise
    except Exception as exc:
        state = _cli_state()
        if state.verbose:
            detail = str(exc) or exc.__class__.__name__
            sys.stderr.write(f"Error: {action} failed: {detail}\n")
        fail_interaction(
            f"{action} failed",
            code="mutation_failed",
            json_output=json_output,
            plain_output=plain_output,
        )


def dry_run_output(
    action: str,
    details: dict[str, Any],
    *,
    plain_columns: list[str] | None = None,
    json_output: bool | None = None,
    plain_output: bool | None = None,
    console: Console | None = None,
) -> None:
    """Render a mutation preview in JSON, TSV, or human table-safe output."""
    if json_output is None or plain_output is None:
        state = _cli_state()
        if json_output is None:
            json_output = bool(state.json_output)
        if plain_output is None:
            plain_output = bool(state.plain_output)

    result: dict[str, Any] = {
        "dryRun": True,
        "status": "success",
        "action": action,
        "message": "DRY RUN, NO CHANGES MADE",
        **details,
    }

    if json_output:
        print_json(result)
        return
    if plain_output:
        columns = plain_columns or list(result)
        print_plain([result], columns=columns)
        return

    (console or Console()).print(
        f"[DRY RUN, NO CHANGES MADE] [green][OK][/green] {action}: "
        + ", ".join(f"{key}={value}" for key, value in details.items())
    )


__all__ = [
    "InteractionPolicy",
    "confirm_destructive",
    "dry_run_output",
    "execute_mutation",
    "fail_interaction",
]
