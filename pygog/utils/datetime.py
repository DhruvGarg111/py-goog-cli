"""Timezone-aware datetime helpers used by calendar commands."""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import tzlocal

from pygog.config import ENV_TIMEZONE, get_config


def _zoneinfo_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown timezone: {name}") from exc


def _system_timezone() -> ZoneInfo:
    """Return the system timezone as an IANA ``ZoneInfo`` instance."""
    try:
        localzone_name = tzlocal.get_localzone_name()
    except (OSError, RuntimeError, ValueError, ZoneInfoNotFoundError):
        localzone_name = None
    if localzone_name:
        try:
            return _zoneinfo_timezone(localzone_name)
        except ValueError:
            pass

    local = datetime.now().astimezone().tzinfo
    key = getattr(local, "key", None)
    if key:
        return _zoneinfo_timezone(key)

    # ``TZ`` is the most reliable portable hint when it is set.
    configured = os.environ.get("TZ")
    if configured:
        return _zoneinfo_timezone(configured)

    # On Unix, /etc/localtime is commonly a symlink into the zoneinfo tree.
    localtime = Path("/etc/localtime")
    try:
        resolved = localtime.resolve()
        marker = f"{os.sep}zoneinfo{os.sep}"
        resolved_text = str(resolved)
        if marker in resolved_text:
            return _zoneinfo_timezone(resolved_text.split(marker, 1)[1])
    except OSError:
        pass

    if local is not None and local.utcoffset(None) == timedelta(0):
        return ZoneInfo("UTC")

    raise ValueError("Could not resolve the system timezone to an IANA timezone")


def resolve_timezone(explicit: str | tzinfo | None = None) -> tzinfo:
    """Resolve a timezone using explicit, environment/config, then system order."""
    if isinstance(explicit, tzinfo):
        return explicit

    name = explicit
    if name is None:
        name = os.environ.get(ENV_TIMEZONE) or get_config().timezone
    if name:
        if name.lower() == "local":
            return _system_timezone()
        return _zoneinfo_timezone(name)
    return _system_timezone()


def now_in_timezone(timezone: tzinfo) -> datetime:
    """Return the current aware datetime in ``timezone``."""
    return datetime.now(timezone)


def _coerce_now(value: datetime | None, timezone: tzinfo) -> datetime:
    current = value if value is not None else now_in_timezone(timezone)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone)
    else:
        current = current.astimezone(timezone)
    return current


def local_day_range(day: date, timezone: tzinfo) -> tuple[datetime, datetime]:
    """Return the aware half-open range covering one local calendar day."""
    start = datetime.combine(day, time.min, tzinfo=timezone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone)
    return start, end


def get_today_range(
    timezone: str | tzinfo | None = None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    tz = resolve_timezone(timezone)
    return local_day_range(_coerce_now(now, tz).date(), tz)


def get_tomorrow_range(
    timezone: str | tzinfo | None = None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    tz = resolve_timezone(timezone)
    day = _coerce_now(now, tz).date() + timedelta(days=1)
    return local_day_range(day, tz)


def get_week_range(
    timezone: str | tzinfo | None = None,
    week_start: int = 0,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    tz = resolve_timezone(timezone)
    current = _coerce_now(now, tz)
    days_since_start = (current.weekday() - week_start) % 7
    start_day = current.date() - timedelta(days=days_since_start)
    start, _ = local_day_range(start_day, tz)
    _, end = local_day_range(start_day + timedelta(days=6), tz)
    return start, end


def get_days_range(
    days: int,
    timezone: str | tzinfo | None = None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    tz = resolve_timezone(timezone)
    current = _coerce_now(now, tz)
    return current, current + timedelta(days=days)


def get_default_range(
    timezone: str | tzinfo | None = None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    return get_days_range(7, timezone, now=now)


def parse_datetime(value: str | datetime, timezone: str | tzinfo | None = None) -> datetime:
    """Parse an ISO datetime and explicitly attach the resolved local timezone."""
    tz = resolve_timezone(timezone)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid datetime: {value}") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=tz)
    return parsed


def serialize_datetime(value: datetime, field_name: str) -> str:
    """Serialize an aware datetime as an RFC3339-compatible ISO string."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.isoformat()


def validate_datetime_string(value: str, field_name: str) -> str:
    """Validate an RFC3339 datetime string without changing its representation."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an RFC3339 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return value
