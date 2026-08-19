"""Plain TSV output formatting."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any


def print_plain(
    data: Sequence[dict[str, Any]],
    columns: list[str] | None = None,
    header: bool = True,
    header_on_empty: bool = False,
) -> None:
    """Print data as plain TSV to stdout.

    Args:
        data: List of dictionaries to display
        columns: Column names to show (defaults to all keys from first row)
        header: Whether to print header row
        header_on_empty: Whether to print explicit columns when data is empty
    """
    if columns is None and data:
        columns = list(data[0].keys())
    elif columns is not None:
        columns = list(columns)
    else:
        columns = []

    if not data:
        if header_on_empty and header and columns:
            print("\t".join(columns), file=sys.stdout)
        return

    if header:
        print("\t".join(columns), file=sys.stdout)

    for row in data:
        values = []
        for col in columns:
            value = row.get(col, "")
            value = "" if value is None else value
            values.append(str(value).replace("\t", " ").replace("\r", " ").replace("\n", " "))
        print("\t".join(values), file=sys.stdout)
