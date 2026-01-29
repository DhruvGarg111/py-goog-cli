"""JSON output formatting."""

from __future__ import annotations

import json
import sys
from typing import Any


def to_json(data: Any, indent: int = 2) -> str:
    """Convert data to JSON string."""
    return json.dumps(data, indent=indent, default=str, ensure_ascii=False)


def print_json(data: Any, indent: int = 2) -> None:
    """Print data as JSON to stdout."""
    print(to_json(data, indent), file=sys.stdout)
