"""Plain TSV output formatting."""

from __future__ import annotations

import sys
from typing import Any, Sequence


def print_plain(
    data: Sequence[dict[str, Any]],
    columns: list[str] | None = None,
    header: bool = True,
) -> None:
    """Print data as plain TSV to stdout.
    
    Args:
        data: List of dictionaries to display
        columns: Column names to show (defaults to all keys from first row)
        header: Whether to print header row
    """
    if not data:
        return

    if columns is None:
        columns = list(data[0].keys())

    if header:
        print("\t".join(columns), file=sys.stdout)

    for row in data:
        values = [str(row.get(col, "")).replace("\t", " ").replace("\n", " ") for col in columns]
        print("\t".join(values), file=sys.stdout)
