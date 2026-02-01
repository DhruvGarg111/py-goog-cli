"""Console utilities for cross-platform output."""

from __future__ import annotations

import sys
from rich.console import Console


def safe_print(console: Console, text: str) -> None:
    """Print text, replacing problematic Unicode on Windows.
    
    Args:
        console: Rich Console instance
        text: Text to print
    """
    try:
        console.print(text)
    except UnicodeEncodeError:
        safe_text = text.replace("✓", "[OK]").replace("✗", "[X]")
        safe_text = safe_text.replace("→", "->").replace("○", "[ ]")
        safe_text = safe_text.replace("·", "-")
        console.print(safe_text)



if sys.platform == "win32":
    OK = "[green][OK][/green]"
    FAIL = "[red][FAIL][/red]"
    WARN = "[yellow][!][/yellow]"
else:
    OK = "[green]✓[/green]"
    FAIL = "[red]✗[/red]"
    WARN = "[yellow]![/yellow]"
