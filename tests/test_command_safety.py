from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import typer

from pygog.cli import state
from pygog.commands import auth, calendar, drive, gmail, tasks


def test_gmail_send_dry_run_does_not_construct_service():
    with patch("pygog.commands.gmail.get_service") as get_service:
        gmail.send_cmd(
            to="person@example.com",
            subject="A subject",
            body="secret body",
            body_html=None,
            body_file=None,
            cc=None,
            bcc=None,
            force=False,
            dry_run=True,
        )

    get_service.assert_not_called()


def test_gmail_thread_modify_dry_run_does_not_construct_service():
    with patch("pygog.commands.gmail.get_service") as get_service:
        gmail.thread_modify(
            thread_id="thread-1",
            add="STARRED",
            remove="INBOX",
            force=False,
            dry_run=True,
        )

    get_service.assert_not_called()


def test_gmail_send_stdin_dry_run_does_not_read_stdin():
    with patch("pygog.commands.gmail.get_service") as get_service:
        gmail.send_cmd(
            to="person@example.com",
            subject="A subject",
            body=None,
            body_html=None,
            body_file="-",
            cc=None,
            bcc=None,
            force=False,
            dry_run=True,
        )

    get_service.assert_not_called()


def test_drive_mutation_dry_runs_do_not_construct_service(tmp_path):
    path = tmp_path / "upload.txt"
    path.write_text("content")
    calls = [
        (
            drive.upload_cmd,
            dict(file_path=path, parent="folder", name="renamed.txt", force=False, dry_run=True),
        ),
        (
            drive.copy_cmd,
            dict(file_id="file", name="copy", parent="folder", force=False, dry_run=True),
        ),
        (drive.mkdir_cmd, dict(name="folder", parent="parent", force=False, dry_run=True)),
        (
            drive.share_cmd,
            dict(
                file_id="file", email="person@example.com", role="reader", force=False, dry_run=True
            ),
        ),
        (
            drive.unshare_cmd,
            dict(file_id="file", permission_id="permission", force=False, dry_run=True),
        ),
    ]

    with patch("pygog.commands.drive.get_service") as get_service:
        for command, kwargs in calls:
            command(**kwargs)

    get_service.assert_not_called()


def test_drive_share_rejects_unknown_role_before_service():
    with patch("pygog.commands.drive.get_service") as get_service:
        with pytest.raises(typer.Exit) as exc_info:
            drive.share_cmd(
                file_id="file",
                email="person@example.com",
                role="owner",
                force=True,
                dry_run=False,
            )

    assert exc_info.value.exit_code == 1
    get_service.assert_not_called()


@pytest.mark.parametrize(
    "command, kwargs",
    [
        (
            calendar.create_cmd,
            dict(
                calendar_id="primary",
                summary="Meeting",
                from_time="2026-01-01T10:00:00+00:00",
                to_time="2026-01-01T11:00:00+00:00",
                description="private details",
                location="Room 1",
                attendees="person@example.com",
                all_day=False,
                send_updates="none",
                force=False,
                dry_run=True,
            ),
        ),
        (
            calendar.update_cmd,
            dict(
                calendar_id="primary",
                event_id="event",
                summary="Updated",
                from_time=None,
                to_time=None,
                description=None,
                location=None,
                send_updates="none",
                force=False,
                dry_run=True,
            ),
        ),
        (
            calendar.delete_cmd,
            dict(
                calendar_id="primary",
                event_id="event",
                send_updates="none",
                force=False,
                dry_run=True,
            ),
        ),
        (
            calendar.respond_cmd,
            dict(
                calendar_id="primary",
                event_id="event",
                status="accepted",
                send_updates="none",
                force=False,
                dry_run=True,
            ),
        ),
    ],
)
def test_calendar_mutation_dry_runs_do_not_construct_service(command, kwargs):
    with patch("pygog.commands.calendar.get_service") as get_service:
        command(**kwargs)

    get_service.assert_not_called()


@pytest.mark.parametrize(
    "command, kwargs",
    [
        (
            tasks.add_cmd,
            dict(
                tasklist_id="list",
                title="Task",
                notes="secret",
                due=None,
                force=False,
                dry_run=True,
            ),
        ),
        (
            tasks.update_cmd,
            dict(
                tasklist_id="list",
                task_id="task",
                title="Updated",
                notes=None,
                due=None,
                force=False,
                dry_run=True,
            ),
        ),
        (tasks.delete_cmd, dict(tasklist_id="list", task_id="task", force=False, dry_run=True)),
        (tasks.clear_cmd, dict(tasklist_id="list", force=False, dry_run=True)),
    ],
)
def test_tasks_mutation_dry_runs_do_not_construct_service(command, kwargs):
    with patch("pygog.commands.tasks.get_service") as get_service:
        command(**kwargs)

    get_service.assert_not_called()


def test_no_input_fails_before_gmail_service_and_confirmation():
    state.no_input = True

    with (
        patch("pygog.commands.gmail.get_service") as get_service,
        patch("pygog.commands.gmail.typer.confirm") as confirm,
    ):
        with pytest.raises(typer.Exit) as exc_info:
            gmail.send_cmd(
                to="person@example.com",
                subject="Subject",
                body="body",
                body_html=None,
                body_file=None,
                cc=None,
                bcc=None,
                force=False,
                dry_run=False,
            )

    assert exc_info.value.exit_code == 1
    get_service.assert_not_called()
    confirm.assert_not_called()


@pytest.mark.parametrize(
    "command, kwargs, service_path",
    [
        (
            drive.rename_cmd,
            dict(file_id="file", name="renamed", force=False, dry_run=False),
            "pygog.commands.drive.get_service",
        ),
        (
            drive.move_cmd,
            dict(file_id="file", parent="folder", force=False, dry_run=False),
            "pygog.commands.drive.get_service",
        ),
        (
            gmail.labels_create,
            dict(name="Label", force=False, dry_run=False),
            "pygog.commands.gmail.get_service",
        ),
        (
            gmail.drafts_create,
            dict(
                to="person@example.com",
                subject="Subject",
                body="SECRET_BODY",
                force=False,
                dry_run=False,
            ),
            "pygog.commands.gmail.get_service",
        ),
        (
            tasks.create_list,
            dict(title="List", force=False, dry_run=False),
            "pygog.commands.tasks.get_service",
        ),
        (
            tasks.done_cmd,
            dict(tasklist_id="list", task_id="task", force=False, dry_run=False),
            "pygog.commands.tasks.get_service",
        ),
        (
            tasks.undo_cmd,
            dict(tasklist_id="list", task_id="task", force=False, dry_run=False),
            "pygog.commands.tasks.get_service",
        ),
    ],
)
def test_remaining_mutations_fail_before_service_without_input(command, kwargs, service_path):
    state.no_input = True

    with patch(service_path) as get_service:
        with pytest.raises(typer.Exit) as exc_info:
            command(**kwargs)

    assert exc_info.value.exit_code == 1
    get_service.assert_not_called()


@pytest.mark.parametrize(
    "command, kwargs, service_path, result",
    [
        (
            drive.rename_cmd,
            dict(file_id="file", name="renamed", force=False, dry_run=False),
            "pygog.commands.drive.get_service",
            {"id": "file", "name": "renamed"},
        ),
        (
            drive.move_cmd,
            dict(file_id="file", parent="folder", force=False, dry_run=False),
            "pygog.commands.drive.get_service",
            {"id": "file", "name": "file"},
        ),
        (
            gmail.labels_create,
            dict(name="Label", force=False, dry_run=False),
            "pygog.commands.gmail.get_service",
            {"id": "label", "name": "Label"},
        ),
        (
            gmail.drafts_create,
            dict(
                to="person@example.com",
                subject="Subject",
                body="SECRET_BODY",
                force=False,
                dry_run=False,
            ),
            "pygog.commands.gmail.get_service",
            {"id": "draft"},
        ),
        (
            tasks.create_list,
            dict(title="List", force=False, dry_run=False),
            "pygog.commands.tasks.get_service",
            {"id": "list"},
        ),
        (
            tasks.done_cmd,
            dict(tasklist_id="list", task_id="task", force=False, dry_run=False),
            "pygog.commands.tasks.get_service",
            {"id": "task", "title": "Task"},
        ),
        (
            tasks.undo_cmd,
            dict(tasklist_id="list", task_id="task", force=False, dry_run=False),
            "pygog.commands.tasks.get_service",
            {"id": "task", "title": "Task"},
        ),
    ],
)
def test_remaining_mutations_honor_global_force(command, kwargs, service_path, result):
    state.force = True
    service = MagicMock()
    service.create_tasklist.return_value = result
    service.complete_task.return_value = result
    service.uncomplete_task.return_value = result
    service.rename_file.return_value = result
    service.move_file.return_value = result
    service.create_label.return_value = result
    service.create_draft.return_value = result

    with patch(service_path, return_value=service) as get_service:
        command(**kwargs)

    get_service.assert_called_once_with()


@pytest.mark.parametrize(
    "command, kwargs, service_path, method_name, result",
    [
        (
            gmail.send_cmd,
            dict(
                to="person@example.com",
                subject="Subject",
                body="SECRET_BODY",
                body_html=None,
                body_file=None,
                cc=None,
                bcc=None,
                force=False,
                dry_run=False,
            ),
            "pygog.commands.gmail.get_service",
            "send_message",
            {"id": "message"},
        ),
        (
            tasks.add_cmd,
            dict(
                tasklist_id="list",
                title="Task",
                notes="SECRET_NOTES",
                due=None,
                force=False,
                dry_run=False,
            ),
            "pygog.commands.tasks.get_service",
            "create_task",
            {"id": "task"},
        ),
        (
            calendar.create_cmd,
            dict(
                calendar_id="primary",
                summary="Meeting",
                from_time="2026-01-01T10:00:00+00:00",
                to_time="2026-01-01T11:00:00+00:00",
                description="SECRET_DESCRIPTION",
                location=None,
                attendees=None,
                all_day=False,
                send_updates="none",
                force=False,
                dry_run=False,
            ),
            "pygog.commands.calendar.get_service",
            "create_event",
            {"id": "event"},
        ),
    ],
)
def test_plain_mutation_success_uses_tsv_without_sensitive_fields(
    capsys,
    command,
    kwargs,
    service_path,
    method_name,
    result,
):
    state.force = True
    state.plain_output = True
    service = MagicMock()
    getattr(service, method_name).return_value = result

    with patch(service_path, return_value=service):
        command(**kwargs)

    output = capsys.readouterr().out
    assert "\t" in output
    assert "SECRET_" not in output


@pytest.mark.parametrize(
    "command, kwargs",
    [
        (
            calendar.create_cmd,
            dict(
                calendar_id="primary",
                summary="Meeting",
                from_time="2026-01-01T10:00:00+00:00",
                to_time="2026-01-01T11:00:00+00:00",
                description=None,
                location=None,
                attendees=None,
                all_day=False,
                send_updates="invalid",
                force=True,
                dry_run=False,
            ),
        ),
        (
            calendar.update_cmd,
            dict(
                calendar_id="primary",
                event_id="event",
                summary=None,
                from_time=None,
                to_time=None,
                description=None,
                location=None,
                send_updates="invalid",
                force=True,
                dry_run=False,
            ),
        ),
        (
            calendar.delete_cmd,
            dict(
                calendar_id="primary",
                event_id="event",
                send_updates="invalid",
                force=True,
                dry_run=False,
            ),
        ),
        (
            calendar.respond_cmd,
            dict(
                calendar_id="primary",
                event_id="event",
                status="accepted",
                send_updates="invalid",
                force=True,
                dry_run=False,
            ),
        ),
    ],
)
def test_calendar_rejects_invalid_send_updates_before_service(command, kwargs):
    with patch("pygog.commands.calendar.get_service") as get_service:
        with pytest.raises(typer.Exit) as exc_info:
            command(**kwargs)

    assert exc_info.value.exit_code == 1
    get_service.assert_not_called()


def test_auth_remove_honors_global_force():
    state.force = True
    client = MagicMock()
    client.remove_account.return_value = True

    with (
        patch("pygog.commands.auth._get_auth_client", return_value=client),
        patch("pygog.commands.auth.typer.confirm") as confirm,
    ):
        auth.remove_cmd(email="person@example.com", client=None, force=False)

    confirm.assert_not_called()
    client.remove_account.assert_called_once_with("person@example.com")


def test_auth_remove_json_not_found_keeps_stdout_machine_readable(capsys):
    state.json_output = True
    client = MagicMock()
    client.remove_account.return_value = False

    with patch("pygog.commands.auth._get_auth_client", return_value=client):
        auth.remove_cmd(email="person@example.com", client=None, force=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload == {"removed": False, "account": "person@example.com"}
