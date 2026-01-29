"""Calendar CLI commands."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from pygog.services.calendar import CalendarService
from pygog.output import print_json, print_plain

app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def get_service() -> CalendarService:
    """Get Calendar service for current account."""
    from pygog.cli import state
    return CalendarService(account=state.account, client=state.client)


def should_json() -> bool:
    from pygog.cli import state
    return state.json_output


def should_plain() -> bool:
    from pygog.cli import state
    return state.plain_output


# =============================================================================
# Calendars
# =============================================================================

@app.command("calendars")
def calendars_cmd():
    """List all calendars."""
    service = get_service()
    calendars = service.list_calendars()

    if should_json():
        print_json({"calendars": calendars})
        return

    if should_plain():
        data = [{"id": c["id"], "summary": c.get("summary", "")} for c in calendars]
        print_plain(data, columns=["id", "summary"])
        return

    table = Table(title="Calendars")
    table.add_column("ID", style="dim", max_width=40)
    table.add_column("Name", style="cyan")
    table.add_column("Access")

    for cal in calendars:
        table.add_row(
            cal["id"],
            cal.get("summary", ""),
            cal.get("accessRole", ""),
        )

    console.print(table)


# =============================================================================
# Events
# =============================================================================

@app.command("events")
def events_cmd(
    calendar_id: str = typer.Argument("primary", help="Calendar ID (default: primary)"),
    today: bool = typer.Option(False, "--today", help="Show today's events"),
    tomorrow: bool = typer.Option(False, "--tomorrow", help="Show tomorrow's events"),
    week: bool = typer.Option(False, "--week", help="Show this week's events"),
    days: Optional[int] = typer.Option(None, "--days", help="Show next N days"),
    from_time: Optional[str] = typer.Option(None, "--from", help="Start time (ISO format or 'today')"),
    to_time: Optional[str] = typer.Option(None, "--to", help="End time (ISO format)"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
):
    """List calendar events."""
    service = get_service()

    # Determine time range
    time_min = None
    time_max = None

    if today:
        time_min, time_max = CalendarService.get_today_range()
    elif tomorrow:
        start, _ = CalendarService.get_today_range()
        time_min = start + timedelta(days=1)
        time_max = time_min + timedelta(days=1)
    elif week:
        time_min, time_max = CalendarService.get_week_range()
    elif days:
        now = datetime.now()
        time_min = now
        time_max = now + timedelta(days=days)
    elif from_time:
        if from_time.lower() == "today":
            time_min, _ = CalendarService.get_today_range()
        else:
            time_min = datetime.fromisoformat(from_time)
        if to_time:
            time_max = datetime.fromisoformat(to_time)
        else:
            time_max = time_min + timedelta(days=30)  # Default 30 days
    else:
        # Default: today + 7 days
        now = datetime.now()
        time_min = now
        time_max = now + timedelta(days=7)

    result = service.list_events(
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
    )
    events = result.get("items", [])

    if should_json():
        print_json(result)
        return

    if not events:
        console.print("[yellow]No events found.[/yellow]")
        return

    # Format for display
    data = []
    for event in events:
        data.append({
            "id": event["id"],
            "summary": event.get("summary", "(no title)"),
            "start": CalendarService.format_event_time(event),
            "location": event.get("location", ""),
        })

    if should_plain():
        print_plain(data, columns=["id", "summary", "start", "location"])
        return

    table = Table(title="Events")
    table.add_column("Time", style="cyan")
    table.add_column("Event", max_width=50)
    table.add_column("Location", max_width=30)
    table.add_column("ID", style="dim")

    for d in data:
        table.add_row(d["start"], d["summary"], d["location"], d["id"])

    console.print(table)


@app.command("event")
def event_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
):
    """Get event details."""
    service = get_service()
    event = service.get_event(calendar_id, event_id)

    if should_json():
        print_json({"event": event})
        return

    console.print(f"[bold]Summary:[/bold] {event.get('summary', '')}")
    console.print(f"[bold]Start:[/bold] {CalendarService.format_event_time(event)}")
    
    end = event.get("end", {})
    end_time = end.get("dateTime", end.get("date", ""))
    console.print(f"[bold]End:[/bold] {end_time}")
    
    if event.get("location"):
        console.print(f"[bold]Location:[/bold] {event['location']}")
    if event.get("description"):
        console.print(f"[bold]Description:[/bold]")
        console.print(event["description"])

    attendees = event.get("attendees", [])
    if attendees:
        console.print(f"\n[bold]Attendees:[/bold]")
        for att in attendees:
            status = att.get("responseStatus", "")
            icon = {"accepted": "[OK]", "declined": "[X]", "tentative": "?", "needsAction": "·"}.get(status, "·")
            console.print(f"  {icon} {att.get('email', '')}")


@app.command("get")
def get_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
):
    """Get event details (alias for 'event')."""
    event_cmd(calendar_id, event_id)


# =============================================================================
# Search
# =============================================================================

@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    today: bool = typer.Option(False, "--today", help="Search today only"),
    days: int = typer.Option(90, "--days", help="Search next N days"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
):
    """Search for events."""
    service = get_service()

    if today:
        time_min, time_max = CalendarService.get_today_range()
    else:
        now = datetime.now()
        time_min = now - timedelta(days=30)  # Also search past 30 days
        time_max = now + timedelta(days=days)

    result = service.list_events(
        calendar_id="primary",
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
        q=query,
    )
    events = result.get("items", [])

    if should_json():
        print_json(result)
        return

    if not events:
        console.print(f"[yellow]No events matching '{query}'[/yellow]")
        return

    table = Table(title=f"Events matching: {query}")
    table.add_column("Time", style="cyan")
    table.add_column("Event", max_width=50)
    table.add_column("ID", style="dim")

    for event in events:
        table.add_row(
            CalendarService.format_event_time(event),
            event.get("summary", "(no title)"),
            event["id"],
        )

    console.print(table)


# =============================================================================
# Create / Update / Delete
# =============================================================================

@app.command("create")
def create_cmd(
    calendar_id: str = typer.Argument("primary", help="Calendar ID"),
    summary: str = typer.Option(..., "--summary", "-s", help="Event title"),
    from_time: str = typer.Option(..., "--from", help="Start time (ISO format)"),
    to_time: str = typer.Option(..., "--to", help="End time (ISO format)"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Location"),
    attendees: Optional[str] = typer.Option(None, "--attendees", help="Comma-separated emails"),
    all_day: bool = typer.Option(False, "--all-day", help="All-day event"),
    send_updates: str = typer.Option("none", "--send-updates", help="all, externalOnly, none"),
):
    """Create a calendar event."""
    service = get_service()

    attendee_list = [a.strip() for a in attendees.split(",")] if attendees else None

    event = service.create_event(
        calendar_id=calendar_id,
        summary=summary,
        start=from_time,
        end=to_time,
        description=description,
        location=location,
        attendees=attendee_list,
        all_day=all_day,
        send_updates=send_updates,
    )

    if should_json():
        print_json({"event": event})
        return

    console.print(f"[green][OK][/green] Event created: [cyan]{summary}[/cyan]")
    console.print(f"  ID: {event['id']}")


@app.command("update")
def update_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
    summary: Optional[str] = typer.Option(None, "--summary", "-s", help="New title"),
    from_time: Optional[str] = typer.Option(None, "--from", help="New start time"),
    to_time: Optional[str] = typer.Option(None, "--to", help="New end time"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="New location"),
    send_updates: str = typer.Option("none", "--send-updates", help="all, externalOnly, none"),
):
    """Update a calendar event."""
    service = get_service()

    event = service.update_event(
        calendar_id=calendar_id,
        event_id=event_id,
        summary=summary,
        start=from_time,
        end=to_time,
        description=description,
        location=location,
        send_updates=send_updates,
    )

    if should_json():
        print_json({"event": event})
        return

    console.print(f"[green][OK][/green] Event updated: {event_id}")


@app.command("delete")
def delete_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
    send_updates: str = typer.Option("none", "--send-updates", help="all, externalOnly, none"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete a calendar event."""
    from pygog.cli import state
    
    if not force and not state.force:
        confirm = typer.confirm(f"Delete event {event_id}?")
        if not confirm:
            raise typer.Exit(0)

    service = get_service()
    service.delete_event(calendar_id, event_id, send_updates=send_updates)

    if should_json():
        print_json({"deleted": True, "eventId": event_id})
        return

    console.print(f"[green][OK][/green] Event deleted: {event_id}")


# =============================================================================
# Respond
# =============================================================================

@app.command("respond")
def respond_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
    status: str = typer.Option(..., "--status", help="accepted, declined, tentative"),
    send_updates: str = typer.Option("none", "--send-updates", help="all, externalOnly, none"),
):
    """Respond to an event invitation."""
    service = get_service()

    if status not in ("accepted", "declined", "tentative"):
        err_console.print(f"[red]Invalid status:[/red] {status}")
        err_console.print("Valid options: accepted, declined, tentative")
        raise typer.Exit(1)

    event = service.respond_to_event(
        calendar_id=calendar_id,
        event_id=event_id,
        status=status,
        send_updates=send_updates,
    )

    if should_json():
        print_json({"event": event})
        return

    console.print(f"[green][OK][/green] Response '{status}' sent for event: {event.get('summary', event_id)}")


# =============================================================================
# Free/Busy
# =============================================================================

@app.command("freebusy")
def freebusy_cmd(
    calendars: str = typer.Option("primary", "--calendars", help="Comma-separated calendar IDs"),
    from_time: str = typer.Option(..., "--from", help="Start time (ISO format)"),
    to_time: str = typer.Option(..., "--to", help="End time (ISO format)"),
):
    """Check free/busy status."""
    service = get_service()

    calendar_list = [c.strip() for c in calendars.split(",")]

    result = service.get_freebusy(
        calendars=calendar_list,
        time_min=from_time,
        time_max=to_time,
    )

    if should_json():
        print_json(result)
        return

    for cal_id, info in result.get("calendars", {}).items():
        console.print(f"\n[bold]{cal_id}[/bold]")
        busy_times = info.get("busy", [])
        if not busy_times:
            console.print("  [green]Free[/green]")
        else:
            for busy in busy_times:
                console.print(f"  [red]Busy:[/red] {busy['start']} - {busy['end']}")
