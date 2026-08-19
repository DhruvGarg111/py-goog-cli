from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import typer

from pygog.cli import state
from pygog.commands import calendar, drive, gmail, tasks
from pygog.errors import ValidationError, emit_error


def _set_json():
    state.json_output = True


def _set_plain():
    state.plain_output = True


def test_gmail_search_json_preserves_provider_shape_and_pagination(capsys):
    _set_json()
    service = MagicMock()
    expected = {
        "threads": [{"id": "thread-1", "historyId": "42"}],
        "nextPageToken": "next-thread-page",
    }
    service.search_threads.return_value = expected

    with patch("pygog.commands.gmail.get_service", return_value=service):
        gmail.search_cmd("from:alice@example.com", max_results=10)

    assert json.loads(capsys.readouterr().out) == expected


def test_gmail_messages_search_plain_uses_stable_columns(capsys):
    _set_plain()
    service = MagicMock()
    service.search_messages.return_value = {
        "messages": [{"id": "message-1", "threadId": "thread-1"}],
        "nextPageToken": "next-message-page",
    }
    service.get_message.return_value = {"id": "message-1", "threadId": "thread-1"}
    service.extract_headers.return_value = {
        "Subject": "Hello",
        "From": "alice@example.com",
        "Date": "Wed, 19 Aug 2026 12:00:00 +0000",
    }

    with patch("pygog.commands.gmail.get_service", return_value=service):
        gmail.messages_search("is:unread", max_results=10, include_body=False)

    assert capsys.readouterr().out == (
        "id\tthread_id\tsubject\tfrom\tdate\n"
        "message-1\tthread-1\tHello\talice@example.com\tWed, 19 Aug 2026 12:00:00 +0000\n"
    )


def test_drive_list_json_preserves_pagination_metadata(capsys):
    _set_json()
    service = MagicMock()
    expected = {
        "files": [{"id": "file-1", "name": "report.txt", "mimeType": "text/plain"}],
        "nextPageToken": "next-file-page",
    }
    service.list_files.return_value = expected

    with patch("pygog.commands.drive.get_service", return_value=service):
        drive.ls_cmd(parent=None, max_results=50)

    assert json.loads(capsys.readouterr().out) == expected


@pytest.mark.parametrize("command_name", ["search", "ls"])
def test_drive_file_lists_plain_emit_stable_columns_for_rows(capsys, command_name):
    _set_plain()
    service = MagicMock()
    service.search_files.return_value = {
        "files": [
            {
                "id": "file-1",
                "name": "report.txt",
                "mimeType": "text/plain",
                "size": "1024",
                "modifiedTime": "2026-08-19T12:00:00Z",
            }
        ]
    }
    service.list_files.return_value = service.search_files.return_value

    with patch("pygog.commands.drive.get_service", return_value=service):
        if command_name == "search":
            drive.search_cmd("report", max_results=50)
        else:
            drive.ls_cmd(parent=None, max_results=50)

    assert capsys.readouterr().out == (
        "id\tname\ttype\tsize\tmodified\nfile-1\treport.txt\tfile\t1.0 KB\t2026-08-19\n"
    )


def test_drive_get_plain_uses_the_same_file_columns_as_lists(capsys):
    _set_plain()
    service = MagicMock()
    service.get_file.return_value = {
        "id": "file-1",
        "name": "report.txt",
        "mimeType": "text/plain",
        "size": "1024",
        "modifiedTime": "2026-08-19T12:00:00Z",
    }

    with patch("pygog.commands.drive.get_service", return_value=service):
        drive.get_cmd("file-1")

    assert capsys.readouterr().out == (
        "id\tname\ttype\tsize\tmodified\nfile-1\treport.txt\tfile\t1.0 KB\t2026-08-19\n"
    )


def test_calendar_events_plain_uses_stable_columns(capsys):
    _set_plain()
    service = MagicMock()
    service.list_events.return_value = {
        "items": [
            {
                "id": "event-1",
                "summary": "Planning",
                "start": {"dateTime": "2026-08-19T12:00:00+00:00"},
                "location": "Room 1",
            }
        ],
        "nextPageToken": "next-event-page",
    }

    with patch("pygog.commands.calendar.get_service", return_value=service):
        calendar.events_cmd(
            calendar_id="primary",
            today=False,
            tomorrow=False,
            week=False,
            days=1,
            from_time=None,
            to_time=None,
            timezone="UTC",
            max_results=50,
        )

    assert capsys.readouterr().out == (
        "id\tsummary\tstart\tlocation\nevent-1\tPlanning\t2026-08-19 12:00\tRoom 1\n"
    )


def test_calendar_search_plain_uses_same_columns_as_events(capsys, monkeypatch):
    _set_plain()
    service = MagicMock()
    service.list_events.return_value = {
        "items": [
            {
                "id": "event-1",
                "summary": "Planning",
                "start": {"date": "2026-08-19"},
            }
        ]
    }
    monkeypatch.setattr(
        calendar.datetime_utils,
        "now_in_timezone",
        lambda tz: calendar.datetime(2026, 8, 19, tzinfo=tz),
    )

    with patch("pygog.commands.calendar.get_service", return_value=service):
        calendar.search_cmd(
            "planning",
            today=False,
            tomorrow=False,
            days=1,
            from_time=None,
            to_time=None,
            timezone="UTC",
            max_results=50,
        )

    assert (
        capsys.readouterr().out == "id\tsummary\tstart\tlocation\nevent-1\tPlanning\t2026-08-19\t\n"
    )


def test_tasks_lists_and_tasks_plain_have_stable_columns(capsys):
    _set_plain()
    service = MagicMock()
    service.list_tasklists.return_value = [{"id": "list-1", "title": "Personal"}]
    service.list_tasks.return_value = [
        {
            "id": "task-1",
            "title": "Ship",
            "status": "needsAction",
            "due": "2026-08-20T00:00:00.000Z",
        }
    ]

    with patch("pygog.commands.tasks.get_service", return_value=service):
        tasks.lists_cmd(max_results=50)
        tasks.list_cmd(tasklist_id="list-1", max_results=50, show_completed=True)

    assert capsys.readouterr().out == (
        "id\ttitle\nlist-1\tPersonal\n"
        "id\ttitle\tstatus\tdue\n"
        "task-1\tShip\tneedsAction\t2026-08-20\n"
    )


def test_plain_list_commands_emit_headers_without_human_diagnostics(capsys):
    _set_plain()
    empty = {"files": []}
    service = MagicMock()
    service.list_files.return_value = empty
    service.search_files.return_value = empty

    with patch("pygog.commands.drive.get_service", return_value=service):
        drive.ls_cmd(parent=None, max_results=50)
        drive.search_cmd("missing", max_results=50)

    assert capsys.readouterr().out == (
        "id\tname\ttype\tsize\tmodified\nid\tname\ttype\tsize\tmodified\n"
    )


def test_all_supported_empty_plain_lists_emit_headers(capsys, monkeypatch):
    _set_plain()
    gmail_service = MagicMock()
    gmail_service.search_threads.return_value = {"threads": []}
    gmail_service.search_messages.return_value = {"messages": []}
    calendar_service = MagicMock()
    calendar_service.list_events.return_value = {"items": []}
    tasks_service = MagicMock()
    tasks_service.list_tasklists.return_value = []
    tasks_service.list_tasks.return_value = []
    monkeypatch.setattr(
        calendar.datetime_utils,
        "now_in_timezone",
        lambda tz: calendar.datetime(2026, 8, 19, tzinfo=tz),
    )

    with patch("pygog.commands.gmail.get_service", return_value=gmail_service):
        gmail.search_cmd("missing", max_results=10)
        gmail.messages_search("missing", max_results=10, include_body=False)
    with patch("pygog.commands.calendar.get_service", return_value=calendar_service):
        calendar.events_cmd(
            calendar_id="primary",
            today=False,
            tomorrow=False,
            week=False,
            days=1,
            from_time=None,
            to_time=None,
            timezone="UTC",
            max_results=50,
        )
        calendar.search_cmd(
            "missing",
            today=False,
            tomorrow=False,
            days=1,
            from_time=None,
            to_time=None,
            timezone="UTC",
            max_results=50,
        )
    with patch("pygog.commands.tasks.get_service", return_value=tasks_service):
        tasks.lists_cmd(max_results=50)
        tasks.list_cmd(tasklist_id="list-1", max_results=50, show_completed=True)

    assert capsys.readouterr().out == (
        "id\tsubject\tfrom\tdate\n"
        "id\tthread_id\tsubject\tfrom\tdate\n"
        "id\tsummary\tstart\tlocation\n"
        "id\tsummary\tstart\tlocation\n"
        "id\ttitle\n"
        "id\ttitle\tstatus\tdue\n"
    )


def test_dry_run_json_is_a_valid_machine_readable_mutation_preview(capsys):
    _set_json()

    with patch("pygog.commands.gmail.get_service") as get_service:
        gmail.send_cmd(
            to="person@example.com",
            subject="Subject",
            body="body",
            body_html=None,
            body_file=None,
            cc=None,
            bcc=None,
            force=False,
            dry_run=True,
        )

    assert json.loads(capsys.readouterr().out) == {
        "dryRun": True,
        "status": "success",
        "action": "send email",
        "message": "DRY RUN, NO CHANGES MADE",
        "to": "person@example.com",
        "subject": "Subject",
        "cc": "",
        "bcc": "",
    }
    get_service.assert_not_called()


def test_json_command_error_is_valid_and_diagnostics_do_not_enter_stdout(capsys):
    _set_json()

    with pytest.raises(typer.Exit) as raised:
        gmail.send_cmd(
            to="person@example.com",
            subject="Subject",
            body=None,
            body_html=None,
            body_file=None,
            cc=None,
            bcc=None,
            force=False,
            dry_run=False,
        )

    assert raised.value.exit_code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "error": {
            "code": "missing_body",
            "message": "No body provided. Use --body, --body-html, or --body-file.",
        }
    }
    assert "Error:" not in captured.out


def test_typed_error_renderer_keeps_json_on_stdout_and_diagnostic_on_stderr(capsys):
    exit_code = emit_error(ValidationError("bad input"), json_output=True)

    captured = capsys.readouterr()
    assert exit_code == 6
    assert json.loads(captured.out) == {
        "error": {"code": "validation_error", "message": "bad input"}
    }
    assert captured.err == "Error [validation_error]: bad input\n"
