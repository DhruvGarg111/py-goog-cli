from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import click
import pytest
from typer.testing import CliRunner

from pygog.commands import calendar as calendar_cmd
from pygog.services.calendar import CalendarService
from pygog.utils import datetime as datetime_utils

runner = CliRunner()


@pytest.fixture
def calendar_service(monkeypatch):
    config = MagicMock()
    config.resolve_account.return_value = "test@example.com"
    config.get_client_for_account.return_value = "test-client"
    monkeypatch.setattr("pygog.services.base.get_config", lambda: config)
    service = CalendarService(account="test@example.com")
    service._service = MagicMock()
    service._service.events.return_value.list.return_value.execute.return_value = {"items": []}
    return service


def _freeze_now(monkeypatch, value):
    monkeypatch.setattr(
        datetime_utils,
        "now_in_timezone",
        lambda tz: value.astimezone(tz),
    )


def test_resolve_timezone_prefers_explicit_over_environment(monkeypatch):
    monkeypatch.setenv("GOG_TIMEZONE", "UTC")

    resolved = datetime_utils.resolve_timezone("Asia/Kolkata")

    assert resolved == ZoneInfo("Asia/Kolkata")


def test_resolve_timezone_uses_environment_before_config(monkeypatch):
    config = MagicMock()
    config.timezone = "Europe/London"
    monkeypatch.setattr(datetime_utils, "get_config", lambda: config)
    monkeypatch.setenv("GOG_TIMEZONE", "Asia/Kolkata")

    assert datetime_utils.resolve_timezone() == ZoneInfo("Asia/Kolkata")


def test_resolve_timezone_uses_config_before_system_local(monkeypatch):
    config = MagicMock()
    config.timezone = "Asia/Kolkata"
    monkeypatch.setattr(datetime_utils, "get_config", lambda: config)
    monkeypatch.delenv("GOG_TIMEZONE", raising=False)

    assert datetime_utils.resolve_timezone() == ZoneInfo("Asia/Kolkata")


def test_resolve_timezone_rejects_unknown_iana_name():
    with pytest.raises(ValueError, match="Unknown timezone"):
        datetime_utils.resolve_timezone("Mars/Olympus_Mons")


def test_today_range_is_aware_and_respects_asia_kolkata_midnight(monkeypatch):
    _freeze_now(
        monkeypatch,
        datetime(2025, 1, 15, 18, 30, tzinfo=ZoneInfo("UTC")),
    )

    start, end = CalendarService.get_today_range("Asia/Kolkata")

    assert start == datetime(2025, 1, 16, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert end == datetime(2025, 1, 17, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert start.tzinfo == ZoneInfo("Asia/Kolkata")
    assert end.tzinfo == ZoneInfo("Asia/Kolkata")


def test_today_range_handles_dst_observing_zone(monkeypatch):
    _freeze_now(
        monkeypatch,
        datetime(2025, 3, 9, 12, 0, tzinfo=ZoneInfo("America/New_York")),
    )

    start, end = CalendarService.get_today_range("America/New_York")

    assert start == datetime(2025, 3, 9, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    assert end == datetime(2025, 3, 10, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    assert start.utcoffset() == timedelta(hours=-5)
    assert end.utcoffset() == timedelta(hours=-4)
    assert (end.astimezone(ZoneInfo("UTC")) - start.astimezone(ZoneInfo("UTC"))) == timedelta(
        hours=23
    )


def test_service_serializes_aware_datetimes_as_rfc3339(calendar_service):
    start = datetime(2025, 1, 16, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    end = datetime(2025, 1, 17, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    calendar_service.list_events(time_min=start, time_max=end)

    kwargs = calendar_service._service.events.return_value.list.call_args.kwargs
    assert kwargs["timeMin"] == "2025-01-16T00:00:00+05:30"
    assert kwargs["timeMax"] == "2025-01-17T00:00:00+05:30"


def test_service_rejects_naive_datetime_filters(calendar_service):
    with pytest.raises(ValueError, match="timezone-aware"):
        calendar_service.list_events(
            time_min=datetime(2025, 1, 16, 0, 0),
            time_max=datetime(2025, 1, 17, 0, 0),
        )


def test_events_today_uses_resolved_timezone_and_aware_range(monkeypatch):
    service = MagicMock()
    service.list_events.return_value = {"items": []}
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)
    _freeze_now(monkeypatch, datetime(2025, 1, 15, 18, 30, tzinfo=ZoneInfo("UTC")))

    result = runner.invoke(
        calendar_cmd.app,
        ["events", "--today", "--timezone", "Asia/Kolkata"],
    )

    assert result.exit_code == 0, click.unstyle(result.output)
    kwargs = service.list_events.call_args.kwargs
    assert kwargs["time_min"] == datetime(2025, 1, 16, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert kwargs["time_max"] == datetime(2025, 1, 17, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert kwargs["time_min"].tzinfo is not None
    assert kwargs["time_max"].tzinfo is not None


def test_events_tomorrow_starts_at_next_local_midnight(monkeypatch):
    service = MagicMock()
    service.list_events.return_value = {"items": []}
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)
    _freeze_now(monkeypatch, datetime(2025, 1, 15, 23, 59, tzinfo=ZoneInfo("UTC")))

    result = runner.invoke(
        calendar_cmd.app,
        ["events", "--tomorrow", "--timezone", "UTC"],
    )

    assert result.exit_code == 0, click.unstyle(result.output)
    kwargs = service.list_events.call_args.kwargs
    assert kwargs["time_min"] == datetime(2025, 1, 16, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert kwargs["time_max"] == datetime(2025, 1, 17, 0, 0, tzinfo=ZoneInfo("UTC"))


def test_events_manual_from_to_interpret_naive_values_in_selected_timezone(monkeypatch):
    service = MagicMock()
    service.list_events.return_value = {"items": []}
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)

    result = runner.invoke(
        calendar_cmd.app,
        [
            "events",
            "--from",
            "2025-01-16T09:00:00",
            "--to",
            "2025-01-16T10:00:00",
            "--timezone",
            "Asia/Kolkata",
        ],
    )

    assert result.exit_code == 0, click.unstyle(result.output)
    kwargs = service.list_events.call_args.kwargs
    assert kwargs["time_min"] == datetime(2025, 1, 16, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert kwargs["time_max"] == datetime(2025, 1, 16, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def test_search_tomorrow_uses_local_day_range(monkeypatch):
    service = MagicMock()
    service.list_events.return_value = {"items": []}
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)
    _freeze_now(monkeypatch, datetime(2025, 1, 15, 18, 30, tzinfo=ZoneInfo("UTC")))

    result = runner.invoke(
        calendar_cmd.app,
        ["search", "planning", "--tomorrow", "--timezone", "Asia/Kolkata"],
    )

    assert result.exit_code == 0, click.unstyle(result.output)
    kwargs = service.list_events.call_args.kwargs
    assert kwargs["time_min"] == datetime(2025, 1, 17, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert kwargs["time_max"] == datetime(2025, 1, 18, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert kwargs["q"] == "planning"


def test_search_manual_from_to_uses_aware_ranges(monkeypatch):
    service = MagicMock()
    service.list_events.return_value = {"items": []}
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)

    result = runner.invoke(
        calendar_cmd.app,
        [
            "search",
            "planning",
            "--from",
            "2025-01-16T09:00:00",
            "--to",
            "2025-01-16T10:00:00",
            "--timezone",
            "Asia/Kolkata",
        ],
    )

    assert result.exit_code == 0, click.unstyle(result.output)
    kwargs = service.list_events.call_args.kwargs
    assert kwargs["time_min"] == datetime(2025, 1, 16, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert kwargs["time_max"] == datetime(2025, 1, 16, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


@pytest.mark.parametrize(
    "args, message",
    [
        (["--today", "--tomorrow"], "cannot be combined"),
        (["--today", "--from", "2025-01-01T00:00:00"], "cannot be combined"),
        (["--to", "2025-01-01T00:00:00"], "--to requires --from"),
    ],
)
def test_search_rejects_incompatible_relative_and_manual_ranges(monkeypatch, args, message):
    service = MagicMock()
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)

    result = runner.invoke(calendar_cmd.app, ["search", "planning", *args])

    assert result.exit_code != 0
    assert message in click.unstyle(result.output)
    service.list_events.assert_not_called()


def test_events_days_and_default_ranges_are_aware(monkeypatch):
    service = MagicMock()
    service.list_events.return_value = {"items": []}
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)
    fixed = datetime(2025, 1, 15, 12, 0, tzinfo=ZoneInfo("UTC"))
    _freeze_now(monkeypatch, fixed)

    for args, expected_min, expected_max in (
        (
            ["events", "--days", "2", "--timezone", "UTC"],
            fixed,
            fixed + timedelta(days=2),
        ),
        (
            ["events", "--timezone", "UTC"],
            fixed,
            fixed + timedelta(days=7),
        ),
    ):
        result = runner.invoke(calendar_cmd.app, args)
        assert result.exit_code == 0, click.unstyle(result.output)
        kwargs = service.list_events.call_args.kwargs
        assert kwargs["time_min"] == expected_min
        assert kwargs["time_max"] == expected_max


def test_events_week_is_local_midnight_to_next_week(monkeypatch):
    service = MagicMock()
    service.list_events.return_value = {"items": []}
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)
    _freeze_now(monkeypatch, datetime(2025, 1, 15, 12, 0, tzinfo=ZoneInfo("UTC")))

    result = runner.invoke(calendar_cmd.app, ["events", "--week", "--timezone", "UTC"])

    assert result.exit_code == 0, click.unstyle(result.output)
    kwargs = service.list_events.call_args.kwargs
    assert kwargs["time_min"] == datetime(2025, 1, 13, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert kwargs["time_max"] == datetime(2025, 1, 20, 0, 0, tzinfo=ZoneInfo("UTC"))


def test_search_today_and_days_ranges_are_aware(monkeypatch):
    service = MagicMock()
    service.list_events.return_value = {"items": []}
    monkeypatch.setattr(calendar_cmd, "get_service", lambda: service)
    fixed = datetime(2025, 1, 15, 12, 0, tzinfo=ZoneInfo("UTC"))
    _freeze_now(monkeypatch, fixed)

    result = runner.invoke(calendar_cmd.app, ["search", "planning", "--today", "--timezone", "UTC"])
    assert result.exit_code == 0, click.unstyle(result.output)
    kwargs = service.list_events.call_args.kwargs
    assert kwargs["time_min"] == datetime(2025, 1, 15, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert kwargs["time_max"] == datetime(2025, 1, 16, 0, 0, tzinfo=ZoneInfo("UTC"))

    result = runner.invoke(
        calendar_cmd.app, ["search", "planning", "--days", "2", "--timezone", "UTC"]
    )
    assert result.exit_code == 0, click.unstyle(result.output)
    kwargs = service.list_events.call_args.kwargs
    assert kwargs["time_min"] == fixed - timedelta(days=30)
    assert kwargs["time_max"] == fixed + timedelta(days=2)


def test_search_rejects_today_and_days_together(monkeypatch):
    result = runner.invoke(calendar_cmd.app, ["search", "planning", "--today", "--days", "2"])

    assert result.exit_code != 0
    assert "cannot be combined" in click.unstyle(result.output)


def test_service_rejects_naive_create_datetime(calendar_service):
    with pytest.raises(ValueError, match="timezone-aware"):
        calendar_service.create_event(
            calendar_id="primary",
            summary="Planning",
            start=datetime(2025, 1, 16, 9, 0),
            end=datetime(2025, 1, 16, 10, 0),
        )


def test_service_interprets_naive_create_datetime_with_explicit_timezone(calendar_service):
    calendar_service._service.events.return_value.insert.return_value.execute.return_value = {
        "id": "event-1"
    }

    calendar_service.create_event(
        calendar_id="primary",
        summary="Planning",
        start=datetime(2025, 1, 16, 9, 0),
        end=datetime(2025, 1, 16, 10, 0),
        timezone="Asia/Kolkata",
    )

    body = calendar_service._service.events.return_value.insert.call_args.kwargs["body"]
    assert body["start"]["dateTime"] == "2025-01-16T09:00:00+05:30"
    assert body["end"]["dateTime"] == "2025-01-16T10:00:00+05:30"


def test_service_formats_all_day_datetime_updates_as_dates(calendar_service):
    calendar_service._service.events.return_value.get.return_value.execute.return_value = {
        "id": "event-1",
        "summary": "Conference",
        "start": {"date": "2025-01-16"},
        "end": {"date": "2025-01-17"},
    }
    calendar_service._service.events.return_value.update.return_value.execute.return_value = {
        "id": "event-1"
    }

    calendar_service.update_event(
        calendar_id="primary",
        event_id="event-1",
        start=datetime(2025, 2, 3, 9, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
        end=datetime(2025, 2, 5, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    body = calendar_service._service.events.return_value.update.call_args.kwargs["body"]
    assert body["start"]["date"] == "2025-02-03"
    assert body["end"]["date"] == "2025-02-05"


def test_system_timezone_uses_tzlocal_iana_name_without_subprocess(monkeypatch):
    resolver = MagicMock()
    resolver.get_localzone_name.return_value = "America/New_York"
    monkeypatch.setattr(datetime_utils, "tzlocal", resolver, raising=False)

    local = timezone(timedelta(hours=1), "Host/Only")
    datetime_class = MagicMock()
    datetime_class.now.return_value.astimezone.return_value.tzinfo = local
    monkeypatch.setattr(datetime_utils, "datetime", datetime_class)

    localtime = MagicMock()
    localtime.resolve.return_value = "C:/not-a-zoneinfo-path"
    monkeypatch.setattr(datetime_utils, "Path", lambda _: localtime)
    subprocess = MagicMock()
    subprocess.check_output.return_value = "Eastern Standard Time"
    monkeypatch.setattr(datetime_utils, "subprocess", subprocess, raising=False)

    assert datetime_utils._system_timezone() == ZoneInfo("America/New_York")
    resolver.get_localzone_name.assert_called_once_with()
    subprocess.check_output.assert_not_called()


def test_system_timezone_returns_safe_error_without_localzone_or_subprocess(monkeypatch):
    resolver = MagicMock()
    resolver.get_localzone_name.side_effect = OSError("registry unavailable")
    monkeypatch.setattr(datetime_utils, "tzlocal", resolver, raising=False)

    local = timezone(timedelta(hours=1), "Host/Only")
    datetime_class = MagicMock()
    datetime_class.now.return_value.astimezone.return_value.tzinfo = local
    monkeypatch.setattr(datetime_utils, "datetime", datetime_class)

    localtime = MagicMock()
    localtime.resolve.return_value = "C:/not-a-zoneinfo-path"
    monkeypatch.setattr(datetime_utils, "Path", lambda _: localtime)
    subprocess = MagicMock()
    monkeypatch.setattr(datetime_utils, "subprocess", subprocess, raising=False)
    monkeypatch.delenv("TZ", raising=False)

    with pytest.raises(ValueError, match="Could not resolve the system timezone"):
        datetime_utils._system_timezone()
    subprocess.check_output.assert_not_called()


@pytest.mark.parametrize(
    ("args", "option_name"),
    [
        (["events", "--from", "not-a-datetime"], "--from"),
        (
            [
                "events",
                "--from",
                "2025-01-16T09:00:00",
                "--to",
                "not-a-datetime",
            ],
            "--to",
        ),
        (["search", "planning", "--from", "not-a-datetime"], "--from"),
        (
            [
                "search",
                "planning",
                "--from",
                "2025-01-16T09:00:00",
                "--to",
                "not-a-datetime",
            ],
            "--to",
        ),
    ],
)
def test_invalid_manual_range_values_use_typer_validation(monkeypatch, args, option_name):
    get_service = MagicMock()
    monkeypatch.setattr(calendar_cmd, "get_service", get_service)

    result = runner.invoke(calendar_cmd.app, [*args, "--timezone", "UTC"])

    assert result.exit_code != 0
    output = click.unstyle(result.output)
    assert option_name in output
    assert "Invalid datetime" in output
    assert "Traceback" not in output
    get_service.assert_not_called()
