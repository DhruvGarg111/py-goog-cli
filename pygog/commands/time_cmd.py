"""Time CLI commands."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
import zoneinfo

import typer
from rich.console import Console

from pygog.config import get_config

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command("now")
def now_cmd(
    timezone: Optional[str] = typer.Option(
        None,
        "--timezone",
        "-tz",
        help="Timezone (IANA name, 'UTC', or 'local')",
    ),
):
    """Display current time."""
    config = get_config()
    tz_name = timezone or config.timezone or "local"

    now = datetime.now()

    if tz_name == "local":
        local_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        console.print(f"Local: {local_str}")
    elif tz_name.upper() == "UTC":
        utc_now = datetime.utcnow()
        utc_str = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
        console.print(f"UTC: {utc_str}")
    else:
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
            tz_now = datetime.now(tz)
            tz_str = tz_now.strftime("%Y-%m-%d %H:%M:%S %Z")
            console.print(f"{tz_name}: {tz_str}")
        except zoneinfo.ZoneInfoNotFoundError:
            console.print(f"[red]Unknown timezone:[/red] {tz_name}")
            raise typer.Exit(1)

    if tz_name != "UTC":
        utc_now = datetime.utcnow()
        console.print(f"UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")
