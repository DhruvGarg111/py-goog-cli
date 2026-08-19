"""Calendar CLI commands."""

from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import NoReturn

import typer
from rich.console import Console
from rich.table import Table

from pygog.interaction import (
    confirm_destructive,
    dry_run_output,
    execute_mutation,
    fail_interaction,
)
from pygog.output import print_json, print_plain
from pygog.services.calendar import CalendarService
from pygog.utils import datetime as datetime_utils

app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)
VALID_SEND_UPDATES = {"all", "externalOnly", "none"}


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


def _account_preview() -> str:
    from pygog.cli import state

    return state.account or "(current account)"


def _event_row(event: dict) -> dict[str, str]:
    """Return the stable TSV representation shared by event list commands."""
    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", "(no title)"),
        "start": CalendarService.format_event_time(event),
        "location": event.get("location", ""),
    }


def _validate_send_updates(send_updates: str) -> None:
    if send_updates not in VALID_SEND_UPDATES:
        fail_interaction(
            f"Invalid send-updates value '{send_updates}'. Valid options: all, externalOnly, none.",
            code="invalid_send_updates",
        )


def _range_error(message: str) -> NoReturn:
    raise typer.BadParameter(message)


def _resolve_command_timezone(name: str | None) -> tzinfo:
    try:
        return datetime_utils.resolve_timezone(name)
    except ValueError as exc:
        _range_error(str(exc))


def _parse_range_value(value: str, timezone: tzinfo, option_name: str) -> datetime:
    lowered = value.strip().lower()
    try:
        if lowered == "today":
            return datetime_utils.get_today_range(timezone)[0]
        if lowered == "tomorrow":
            return datetime_utils.get_tomorrow_range(timezone)[0]
        return datetime_utils.parse_datetime(value, timezone)
    except ValueError as exc:
        _range_error(f"{option_name}: {exc}")


def _validate_range_options(
    *,
    today: bool,
    tomorrow: bool,
    week: bool,
    days: int | None,
    from_time: str | None,
    to_time: str | None,
) -> None:
    relative = [
        name
        for name, selected in (
            ("--today", today),
            ("--tomorrow", tomorrow),
            ("--week", week),
            ("--days", days is not None),
        )
        if selected
    ]
    if len(relative) > 1:
        _range_error(f"{', '.join(relative)} cannot be combined")
    if from_time and relative:
        _range_error(f"{from_time!r} cannot be combined with {relative[0]}")
    if to_time and not from_time:
        _range_error("--to requires --from")


def _event_range(
    *,
    timezone: tzinfo,
    today: bool,
    tomorrow: bool,
    week: bool,
    days: int | None,
    from_time: str | None,
    to_time: str | None,
) -> tuple[datetime, datetime]:
    _validate_range_options(
        today=today,
        tomorrow=tomorrow,
        week=week,
        days=days,
        from_time=from_time,
        to_time=to_time,
    )
    if days is not None and days <= 0:
        _range_error("--days must be greater than zero")

    if today:
        return datetime_utils.get_today_range(timezone)
    if tomorrow:
        return datetime_utils.get_tomorrow_range(timezone)
    if week:
        return datetime_utils.get_week_range(timezone)
    if days is not None:
        return datetime_utils.get_days_range(days, timezone)
    if from_time:
        start = _parse_range_value(from_time, timezone, "--from")
        end = (
            _parse_range_value(to_time, timezone, "--to") if to_time else start + timedelta(days=30)
        )
        if end <= start:
            _range_error("--to must be after --from")
        return start, end
    return datetime_utils.get_default_range(timezone)


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
        print_plain(data, columns=["id", "summary"], header_on_empty=True)
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


@app.command("events")
def events_cmd(
    calendar_id: str = typer.Argument("primary", help="Calendar ID (default: primary)"),
    today: bool = typer.Option(False, "--today", help="Show today's events"),
    tomorrow: bool = typer.Option(False, "--tomorrow", help="Show tomorrow's events"),
    week: bool = typer.Option(False, "--week", help="Show this week's events"),
    days: int | None = typer.Option(None, "--days", help="Show next N days"),
    from_time: str | None = typer.Option(None, "--from", help="Start time (ISO format or 'today')"),
    to_time: str | None = typer.Option(None, "--to", help="End time (ISO format)"),
    timezone: str | None = typer.Option(None, "--timezone", help="Timezone (IANA name)"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
):
    """List calendar events."""
    resolved_timezone = _resolve_command_timezone(timezone)
    time_min, time_max = _event_range(
        timezone=resolved_timezone,
        today=today,
        tomorrow=tomorrow,
        week=week,
        days=days,
        from_time=from_time,
        to_time=to_time,
    )
    service = get_service()

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

    data = [_event_row(event) for event in events]

    if should_plain():
        print_plain(data, columns=["id", "summary", "start", "location"], header_on_empty=True)
        return

    if not events:
        console.print("[yellow]No events found.[/yellow]")
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
        console.print("[bold]Description:[/bold]")
        console.print(event["description"])

    attendees = event.get("attendees", [])
    if attendees:
        console.print("\n[bold]Attendees:[/bold]")
        for att in attendees:
            status = att.get("responseStatus", "")
            icon = {
                "accepted": "[OK]",
                "declined": "[X]",
                "tentative": "?",
                "needsAction": "·",
            }.get(status, "·")
            console.print(f"  {icon} {att.get('email', '')}")


@app.command("get")
def get_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
):
    """Get event details (alias for 'event')."""
    event_cmd(calendar_id, event_id)


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search query"),
    today: bool = typer.Option(False, "--today", help="Search today only"),
    tomorrow: bool = typer.Option(False, "--tomorrow", help="Search tomorrow only"),
    days: int | None = typer.Option(None, "--days", help="Search next N days (default: 90)"),
    from_time: str | None = typer.Option(None, "--from", help="Start time (ISO format or 'today')"),
    to_time: str | None = typer.Option(None, "--to", help="End time (ISO format)"),
    timezone: str | None = typer.Option(None, "--timezone", help="Timezone (IANA name)"),
    max_results: int = typer.Option(50, "--max", "-m", help="Maximum results"),
):
    """Search for events."""
    resolved_timezone = _resolve_command_timezone(timezone)
    relative = [
        name
        for name, selected in (
            ("--today", today),
            ("--tomorrow", tomorrow),
            ("--days", days is not None),
        )
        if selected
    ]
    if len(relative) > 1:
        _range_error(f"{', '.join(relative)} cannot be combined")
    if (today or tomorrow or days is not None) and (from_time or to_time):
        _range_error("relative date options cannot be combined with --from/--to")
    if to_time and not from_time:
        _range_error("--to requires --from")
    if days is not None and days <= 0:
        _range_error("--days must be greater than zero")

    if today:
        time_min, time_max = datetime_utils.get_today_range(resolved_timezone)
    elif tomorrow:
        time_min, time_max = datetime_utils.get_tomorrow_range(resolved_timezone)
    elif from_time:
        time_min = _parse_range_value(from_time, resolved_timezone, "--from")
        time_max = (
            _parse_range_value(to_time, resolved_timezone, "--to")
            if to_time
            else time_min + timedelta(days=30)
        )
        if time_max <= time_min:
            _range_error("--to must be after --from")
    else:
        current = datetime_utils.now_in_timezone(resolved_timezone)
        time_min = current - timedelta(days=30)
        time_max = current + timedelta(days=days if days is not None else 90)

    service = get_service()

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

    data = [_event_row(event) for event in events]

    if should_plain():
        print_plain(data, columns=["id", "summary", "start", "location"], header_on_empty=True)
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


@app.command("create")
def create_cmd(
    calendar_id: str = typer.Argument("primary", help="Calendar ID"),
    summary: str = typer.Option(..., "--summary", "-s", help="Event title"),
    from_time: str = typer.Option(..., "--from", help="Start time (ISO format)"),
    to_time: str = typer.Option(..., "--to", help="End time (ISO format)"),
    description: str | None = typer.Option(None, "--description", "-d", help="Description"),
    location: str | None = typer.Option(None, "--location", "-l", help="Location"),
    attendees: str | None = typer.Option(None, "--attendees", help="Comma-separated emails"),
    all_day: bool = typer.Option(False, "--all-day", help="All-day event"),
    send_updates: str = typer.Option("none", "--send-updates", help="all, externalOnly, none"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Create a calendar event."""
    _validate_send_updates(send_updates)
    attendee_list = [a.strip() for a in attendees.split(",")] if attendees else None

    details = {
        "calendarId": calendar_id,
        "summary": summary,
        "from": from_time,
        "to": to_time,
        "attendees": ",".join(attendee_list or []),
    }
    if dry_run:
        dry_run_output(
            "create calendar event",
            details,
            plain_columns=["dryRun", "action", "calendarId", "summary", "from", "to", "attendees"],
            console=console,
        )
        return

    confirm_destructive(
        "create calendar event",
        f"calendar={calendar_id}, summary={summary!r}, from={from_time}, to={to_time}, "
        f"attendees={','.join(attendee_list or []) or '(none)'}, account={_account_preview()}",
        local_force=force,
    )
    event = execute_mutation(
        lambda: get_service().create_event(
            calendar_id=calendar_id,
            summary=summary,
            start=from_time,
            end=to_time,
            description=description,
            location=location,
            attendees=attendee_list,
            all_day=all_day,
            send_updates=send_updates,
        ),
        action="create calendar event",
    )

    if should_json():
        print_json({"event": event})
        return

    if should_plain():
        print_plain(
            [
                {
                    "eventId": event.get("id", ""),
                    "summary": summary,
                    "from": from_time,
                    "to": to_time,
                }
            ],
            columns=["eventId", "summary", "from", "to"],
        )
        return

    console.print(f"[green][OK][/green] Event created: [cyan]{summary}[/cyan]")
    console.print(f"  ID: {event['id']}")


@app.command("update")
def update_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
    summary: str | None = typer.Option(None, "--summary", "-s", help="New title"),
    from_time: str | None = typer.Option(None, "--from", help="New start time"),
    to_time: str | None = typer.Option(None, "--to", help="New end time"),
    description: str | None = typer.Option(None, "--description", "-d", help="New description"),
    location: str | None = typer.Option(None, "--location", "-l", help="New location"),
    send_updates: str = typer.Option("none", "--send-updates", help="all, externalOnly, none"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Update a calendar event."""
    _validate_send_updates(send_updates)
    changes = {
        key: value
        for key, value in (
            ("summary", summary),
            ("from", from_time),
            ("to", to_time),
            ("location", location),
        )
        if value is not None
    }
    details = {"calendarId": calendar_id, "eventId": event_id, **changes}
    if dry_run:
        dry_run_output(
            "update calendar event",
            details,
            plain_columns=["dryRun", "action", "calendarId", "eventId", *changes.keys()],
            console=console,
        )
        return

    confirm_destructive(
        "update calendar event",
        f"calendar={calendar_id}, event={event_id}, changes={changes or '(none)'}, "
        f"account={_account_preview()}",
        local_force=force,
    )
    event = execute_mutation(
        lambda: get_service().update_event(
            calendar_id=calendar_id,
            event_id=event_id,
            summary=summary,
            start=from_time,
            end=to_time,
            description=description,
            location=location,
            send_updates=send_updates,
        ),
        action="update calendar event",
    )

    if should_json():
        print_json({"event": event})
        return

    if should_plain():
        print_plain(
            [{"eventId": event.get("id", event_id), **changes}],
            columns=["eventId", *changes.keys()],
        )
        return

    console.print(f"[green][OK][/green] Event updated: {event_id}")


@app.command("delete")
def delete_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
    send_updates: str = typer.Option("none", "--send-updates", help="all, externalOnly, none"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Delete a calendar event."""
    _validate_send_updates(send_updates)
    if dry_run:
        dry_run_output(
            "delete calendar event",
            {"calendarId": calendar_id, "eventId": event_id, "sendUpdates": send_updates},
            plain_columns=["dryRun", "action", "calendarId", "eventId", "sendUpdates"],
            console=console,
        )
        return

    confirm_destructive(
        "delete calendar event",
        f"calendar={calendar_id}, event={event_id}, account={_account_preview()}",
        local_force=force,
    )

    execute_mutation(
        lambda: get_service().delete_event(calendar_id, event_id, send_updates=send_updates),
        action="delete calendar event",
    )

    if should_json():
        print_json({"deleted": True, "eventId": event_id})
        return

    if should_plain():
        print_plain([{"deleted": True, "eventId": event_id}], columns=["deleted", "eventId"])
        return

    console.print(f"[green][OK][/green] Event deleted: {event_id}")


@app.command("respond")
def respond_cmd(
    calendar_id: str = typer.Argument(..., help="Calendar ID"),
    event_id: str = typer.Argument(..., help="Event ID"),
    status: str = typer.Option(..., "--status", help="accepted, declined, tentative"),
    send_updates: str = typer.Option("none", "--send-updates", help="all, externalOnly, none"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the action without executing"),
):
    """Respond to an event invitation."""
    _validate_send_updates(send_updates)
    if status not in ("accepted", "declined", "tentative"):
        fail_interaction(
            f"Invalid status '{status}'. Valid options: accepted, declined, tentative.",
            code="invalid_status",
        )

    if dry_run:
        dry_run_output(
            "respond to calendar event",
            {
                "calendarId": calendar_id,
                "eventId": event_id,
                "status": status,
                "sendUpdates": send_updates,
            },
            plain_columns=["dryRun", "action", "calendarId", "eventId", "status", "sendUpdates"],
            console=console,
        )
        return

    confirm_destructive(
        "respond to calendar event",
        f"calendar={calendar_id}, event={event_id}, status={status}, account={_account_preview()}",
        local_force=force,
    )
    event = execute_mutation(
        lambda: get_service().respond_to_event(
            calendar_id=calendar_id,
            event_id=event_id,
            status=status,
            send_updates=send_updates,
        ),
        action="respond to calendar event",
    )

    if should_json():
        print_json({"event": event})
        return

    if should_plain():
        print_plain(
            [{"eventId": event.get("id", event_id), "status": status}],
            columns=["eventId", "status"],
        )
        return

    console.print(
        f"[green][OK][/green] Response '{status}' sent for event: {event.get('summary', event_id)}"
    )


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
