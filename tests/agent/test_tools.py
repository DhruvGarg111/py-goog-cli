from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pygog.agent.tools as agent_tools


class FakeDriveService:
    def __init__(self, *, list_response=None, search_response=None):
        self.list_response = list_response if list_response is not None else {}
        self.search_response = search_response if search_response is not None else {}
        self.list_calls = []
        self.search_calls = []

    def list_files(self, **kwargs):
        self.list_calls.append(kwargs)
        return self.list_response

    def search_files(self, **kwargs):
        self.search_calls.append(kwargs)
        return self.search_response


class FakeCalendarService:
    def __init__(self, *, list_response=None, create_response=None):
        self.list_response = list_response if list_response is not None else {}
        self.create_response = create_response if create_response is not None else {"id": "event-1"}
        self.list_calls = []
        self.create_calls = []

    def list_events(self, **kwargs):
        self.list_calls.append(kwargs)
        return self.list_response

    def create_event(self, **kwargs):
        self.create_calls.append(kwargs)
        return self.create_response


def test_drive_list_passes_folder_id_and_normalizes_response():
    service = FakeDriveService(
        list_response={
            "files": [
                {
                    "id": "folder-1",
                    "name": "Projects",
                    "mimeType": "application/vnd.google-apps.folder",
                    "modifiedTime": "2026-08-19T10:00:00Z",
                },
                {
                    "id": "file-1",
                    "name": "plan.txt",
                    "mimeType": "text/plain",
                    "modifiedTime": "2026-08-18T09:00:00Z",
                },
            ]
        }
    )

    with patch("pygog.services.drive.DriveService", return_value=service) as drive_service:
        result = agent_tools.drive_list(
            folder_id="folder-1", max_results=2, account="user@example.com"
        )

    drive_service.assert_called_once_with(account="user@example.com")
    assert service.list_calls == [{"parent_id": "folder-1", "max_results": 2}]
    assert result == [
        {
            "id": "folder-1",
            "name": "Projects",
            "type": "folder",
            "mime_type": "application/vnd.google-apps.folder",
            "modified": "2026-08-19T10:00:00Z",
        },
        {
            "id": "file-1",
            "name": "plan.txt",
            "type": "file",
            "mime_type": "text/plain",
            "modified": "2026-08-18T09:00:00Z",
        },
    ]


def test_drive_list_returns_empty_list_for_empty_or_missing_files():
    for response in ({"files": []}, {}):
        service = FakeDriveService(list_response=response)

        with patch("pygog.services.drive.DriveService", return_value=service):
            result = agent_tools.drive_list(folder_id=None, max_results=5)

        assert service.list_calls == [{"parent_id": None, "max_results": 5}]
        assert result == []


def test_drive_search_passes_plain_term_and_normalizes_response():
    service = FakeDriveService(
        search_response={
            "files": [
                {
                    "id": "file-2",
                    "name": "quarterly report.pdf",
                    "mimeType": "application/pdf",
                    "webViewLink": "https://drive.google.com/file/d/file-2/view",
                }
            ]
        }
    )

    with patch("pygog.services.drive.DriveService", return_value=service):
        result = agent_tools.drive_search(
            query="quarterly report", max_results=3, account="user@example.com"
        )

    assert service.search_calls == [{"query": "quarterly report", "max_results": 3}]
    assert result == [
        {
            "id": "file-2",
            "name": "quarterly report.pdf",
            "type": "file",
            "mime_type": "application/pdf",
            "web_link": "https://drive.google.com/file/d/file-2/view",
        }
    ]


def test_drive_search_returns_empty_list_for_empty_or_missing_files():
    for response in ({"files": []}, {}):
        service = FakeDriveService(search_response=response)

        with patch("pygog.services.drive.DriveService", return_value=service):
            result = agent_tools.drive_search(query="report", max_results=5)

        assert service.search_calls == [{"query": "report", "max_results": 5}]
        assert result == []


def test_calendar_events_uses_aware_now_in_resolved_timezone():
    service = FakeCalendarService()
    resolved_timezone = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 8, 19, 9, 30, tzinfo=resolved_timezone)

    with (
        patch("pygog.services.calendar.CalendarService", return_value=service),
        patch(
            "pygog.utils.datetime.resolve_timezone", return_value=resolved_timezone
        ) as resolve_timezone,
        patch("pygog.utils.datetime.now_in_timezone", return_value=now) as now_in_timezone,
    ):
        result = agent_tools.calendar_events(days=3)

    resolve_timezone.assert_called_once_with()
    now_in_timezone.assert_called_once_with(resolved_timezone)
    assert service.list_calls == [
        {
            "calendar_id": "primary",
            "time_min": now,
            "time_max": now + timedelta(days=3),
        }
    ]
    assert result == []


def test_calendar_search_uses_aware_now_in_resolved_timezone():
    service = FakeCalendarService()
    resolved_timezone = ZoneInfo("America/New_York")
    now = datetime(2026, 8, 19, 9, 30, tzinfo=resolved_timezone)

    with (
        patch("pygog.services.calendar.CalendarService", return_value=service),
        patch("pygog.utils.datetime.resolve_timezone", return_value=resolved_timezone),
        patch("pygog.utils.datetime.now_in_timezone", return_value=now),
    ):
        result = agent_tools.calendar_search(query="planning", days=10)

    assert service.list_calls == [
        {
            "calendar_id": "primary",
            "time_min": now - timedelta(days=30),
            "time_max": now + timedelta(days=10),
            "q": "planning",
        }
    ]
    assert result == []


def test_calendar_create_passes_resolved_timezone_for_naive_iso_times():
    service = FakeCalendarService()
    resolved_timezone = ZoneInfo("Asia/Kolkata")

    with (
        patch("pygog.services.calendar.CalendarService", return_value=service),
        patch("pygog.utils.datetime.resolve_timezone", return_value=resolved_timezone),
    ):
        agent_tools.calendar_create(
            summary="Planning",
            start_time="2026-08-19T09:30:00",
            end_time="2026-08-19T10:30:00",
        )

    call = service.create_calls[0]
    assert call["start"] == "2026-08-19T09:30:00"
    assert call["end"] == "2026-08-19T10:30:00"
    assert call["timezone"] == "Asia/Kolkata"


def test_calendar_create_preserves_aware_iso_times():
    service = FakeCalendarService()

    with patch("pygog.services.calendar.CalendarService", return_value=service):
        agent_tools.calendar_create(
            summary="Planning",
            start_time="2026-08-19T09:30:00Z",
            end_time="2026-08-19T10:30:00+00:00",
            timezone="Asia/Kolkata",
        )

    call = service.create_calls[0]
    assert call["start"] == "2026-08-19T09:30:00Z"
    assert call["end"] == "2026-08-19T10:30:00+00:00"
