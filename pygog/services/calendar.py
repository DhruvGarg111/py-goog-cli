"""Calendar API service wrapper."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from pygog.services.base import BaseService
from pygog.utils import datetime as datetime_utils


def _serialize_event_datetime(
    value: datetime | str,
    field_name: str,
    timezone: str | None = None,
) -> str:
    """Serialize an event datetime, interpreting naive values only explicitly."""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            if timezone is None:
                return datetime_utils.serialize_datetime(value, field_name)
            value = value.replace(tzinfo=datetime_utils.resolve_timezone(timezone))
        return datetime_utils.serialize_datetime(value, field_name)

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a datetime or RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an RFC3339 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if timezone is None:
            raise ValueError(f"{field_name} must include a timezone")
        parsed = parsed.replace(tzinfo=datetime_utils.resolve_timezone(timezone))
        return datetime_utils.serialize_datetime(parsed, field_name)
    return value


class CalendarService(BaseService):
    """Calendar API service wrapper."""

    SERVICE_NAME = "calendar"
    SERVICE_VERSION = "v3"

    def _events(self):
        """Get events API."""
        return self._get_service().events()

    def _calendars(self):
        """Get calendars API."""
        return self._get_service().calendars()

    def _calendar_list(self):
        """Get calendarList API."""
        return self._get_service().calendarList()

    def list_calendars(self) -> list[dict[str, Any]]:
        """List all calendars.

        Returns:
            List of calendar dicts
        """
        result = self._execute(self._calendar_list().list())
        return cast(list[dict[str, Any]], result.get("items", []))

    def get_calendar(self, calendar_id: str) -> dict[str, Any]:
        """Get calendar details.

        Args:
            calendar_id: Calendar ID (or 'primary')

        Returns:
            Calendar dict
        """
        return self._execute(self._calendars().get(calendarId=calendar_id))

    def list_events(
        self,
        calendar_id: str = "primary",
        time_min: datetime | str | None = None,
        time_max: datetime | str | None = None,
        max_results: int = 100,
        single_events: bool = True,
        order_by: str = "startTime",
        page_token: str | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        """List events from a calendar.

        Args:
            calendar_id: Calendar ID (or 'primary')
            time_min: Start time filter (ISO format or datetime)
            time_max: End time filter (ISO format or datetime)
            max_results: Maximum events to return
            single_events: Expand recurring events
            order_by: 'startTime' or 'updated'
            page_token: Token for pagination
            q: Free text search query

        Returns:
            Dict with 'items' list and optional 'nextPageToken'
        """
        params = {
            "calendarId": calendar_id,
            "maxResults": max_results,
            "singleEvents": single_events,
        }

        if time_min is not None:
            if isinstance(time_min, datetime):
                time_min = datetime_utils.serialize_datetime(time_min, "time_min")
            elif isinstance(time_min, str):
                time_min = datetime_utils.validate_datetime_string(time_min, "time_min")
            params["timeMin"] = time_min

        if time_max is not None:
            if isinstance(time_max, datetime):
                time_max = datetime_utils.serialize_datetime(time_max, "time_max")
            elif isinstance(time_max, str):
                time_max = datetime_utils.validate_datetime_string(time_max, "time_max")
            params["timeMax"] = time_max

        if single_events:
            params["orderBy"] = order_by

        if page_token:
            params["pageToken"] = page_token

        if q:
            params["q"] = q

        return self._execute(self._events().list(**params))

    def get_event(self, calendar_id: str, event_id: str) -> dict[str, Any]:
        """Get an event by ID.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID

        Returns:
            Event dict
        """
        return self._execute(self._events().get(calendarId=calendar_id, eventId=event_id))

    def create_event(
        self,
        calendar_id: str,
        summary: str,
        start: datetime | str,
        end: datetime | str,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        all_day: bool = False,
        timezone: str | None = None,
        send_updates: str = "none",
        recurrence: list[str] | None = None,
        reminders: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a calendar event.

        Args:
            calendar_id: Calendar ID
            summary: Event title
            start: Start time
            end: End time
            description: Event description
            location: Event location
            attendees: List of attendee emails
            all_day: Whether this is an all-day event
            timezone: Timezone for the event
            send_updates: 'all', 'externalOnly', or 'none'
            recurrence: List of RRULE strings
            reminders: Reminder configuration

        Returns:
            Created event dict
        """
        event: dict[str, Any] = {"summary": summary}

        if all_day:
            if isinstance(start, datetime):
                start = start.strftime("%Y-%m-%d")
            if isinstance(end, datetime):
                end = end.strftime("%Y-%m-%d")
            event["start"] = {"date": start}
            event["end"] = {"date": end}
        else:
            start = _serialize_event_datetime(start, "start", timezone)
            end = _serialize_event_datetime(end, "end", timezone)

            start_obj = {"dateTime": start}
            end_obj = {"dateTime": end}

            if timezone:
                start_obj["timeZone"] = timezone
                end_obj["timeZone"] = timezone

            event["start"] = start_obj
            event["end"] = end_obj

        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        if recurrence:
            event["recurrence"] = recurrence
        if reminders:
            event["reminders"] = reminders

        return cast(
            dict[str, Any],
            (
                self._events()
                .insert(
                    calendarId=calendar_id,
                    body=event,
                    sendUpdates=send_updates,
                )
                .execute()
            ),
        )

    def update_event(
        self,
        calendar_id: str,
        event_id: str,
        summary: str | None = None,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        description: str | None = None,
        location: str | None = None,
        send_updates: str = "none",
    ) -> dict[str, Any]:
        """Update an event.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            summary: New title
            start: New start time
            end: New end time
            description: New description
            location: New location
            send_updates: 'all', 'externalOnly', or 'none'

        Returns:
            Updated event dict
        """
        event = self.get_event(calendar_id, event_id)

        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location
        if start is not None:
            if "dateTime" in event.get("start", {}):
                event["start"]["dateTime"] = _serialize_event_datetime(
                    start,
                    "start",
                    event["start"].get("timeZone"),
                )
            else:
                event["start"]["date"] = start
        if end is not None:
            if "dateTime" in event.get("end", {}):
                event["end"]["dateTime"] = _serialize_event_datetime(
                    end,
                    "end",
                    event["end"].get("timeZone"),
                )
            else:
                event["end"]["date"] = end

        return cast(
            dict[str, Any],
            (
                self._events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates=send_updates,
                )
                .execute()
            ),
        )

    def delete_event(
        self,
        calendar_id: str,
        event_id: str,
        send_updates: str = "none",
    ) -> None:
        """Delete an event.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            send_updates: 'all', 'externalOnly', or 'none'
        """
        self._events().delete(
            calendarId=calendar_id,
            eventId=event_id,
            sendUpdates=send_updates,
        ).execute()

    def respond_to_event(
        self,
        calendar_id: str,
        event_id: str,
        status: str,
        send_updates: str = "none",
    ) -> dict[str, Any]:
        """Respond to an event invitation.

        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            status: 'accepted', 'declined', or 'tentative'
            send_updates: 'all', 'externalOnly', or 'none'

        Returns:
            Updated event dict
        """
        event = self.get_event(calendar_id, event_id)

        attendees = event.get("attendees", [])
        for attendee in attendees:
            if attendee.get("self"):
                attendee["responseStatus"] = status
                break

        return cast(
            dict[str, Any],
            (
                self._events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates=send_updates,
                )
                .execute()
            ),
        )

    def get_freebusy(
        self,
        calendars: list[str],
        time_min: datetime | str,
        time_max: datetime | str,
    ) -> dict[str, Any]:
        """Get free/busy information.

        Args:
            calendars: List of calendar IDs
            time_min: Start of time range
            time_max: End of time range

        Returns:
            Free/busy response dict
        """
        if isinstance(time_min, datetime):
            time_min = datetime_utils.serialize_datetime(time_min, "time_min")
        elif isinstance(time_min, str):
            time_min = datetime_utils.validate_datetime_string(time_min, "time_min")
        if isinstance(time_max, datetime):
            time_max = datetime_utils.serialize_datetime(time_max, "time_max")
        elif isinstance(time_max, str):
            time_max = datetime_utils.validate_datetime_string(time_max, "time_max")

        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": cal} for cal in calendars],
        }

        return self._execute(self._get_service().freebusy().query(body=body))

    @staticmethod
    def get_today_range(timezone: str | None = None):
        """Get start/end of today.

        Args:
            timezone: Timezone name

        Returns:
            Tuple of (start, end) datetime objects
        """
        return datetime_utils.get_today_range(timezone)

    @staticmethod
    def get_week_range(timezone: str | None = None, week_start: int = 0):
        """Get start/end of current week.

        Args:
            timezone: Timezone name
            week_start: Week start day (0=Monday, 6=Sunday)

        Returns:
            Tuple of (start, end) datetime objects
        """
        return datetime_utils.get_week_range(timezone, week_start)

    @staticmethod
    def format_event_time(event: dict[str, Any]) -> str:
        """Format event start time for display.

        Args:
            event: Event dict

        Returns:
            Formatted time string
        """
        start = event.get("start", {})
        if "date" in start:
            return cast(str, start["date"])  # All-day event
        elif "dateTime" in start:
            dt_str = start["dateTime"]
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                return cast(str, dt_str)
        return ""
