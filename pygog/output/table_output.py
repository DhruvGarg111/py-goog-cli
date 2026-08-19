"""Table output formatting using Rich."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rich.console import Console
from rich.table import Table


def print_table(
    data: Sequence[dict[str, Any]],
    columns: list[str] | None = None,
    title: str | None = None,
    console: Console | None = None,
) -> None:
    """Print data as a rich table.

    Args:
        data: List of dictionaries to display
        columns: Column names to show (defaults to all keys from first row)
        title: Optional table title
        console: Rich console to use (defaults to stdout)
    """
    if console is None:
        console = Console()

    if not data:
        console.print("[dim]No data to display[/dim]")
        return

    if columns is None:
        columns = list(data[0].keys())

    table = Table(title=title, show_header=True, header_style="bold cyan")

    for col in columns:
        table.add_column(col.upper().replace("_", " "))

    for row in data:
        values = [str(row.get(col, "")) for col in columns]
        table.add_row(*values)

    console.print(table)


def print_single(
    data: dict[str, Any],
    console: Console | None = None,
) -> None:
    """Print a single record as key-value pairs."""
    if console is None:
        console = Console()

    table = Table(show_header=False, box=None)
    table.add_column("Key", style="bold")
    table.add_column("Value")

    for key, value in data.items():
        table.add_row(key, str(value) if value is not None else "")

    console.print(table)
