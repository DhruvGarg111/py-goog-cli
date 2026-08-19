from __future__ import annotations

import json
from unittest.mock import patch

import pytest
import typer

from pygog.cli import state
from pygog.errors import ConfigurationError, ValidationError
from pygog.interaction import (
    InteractionPolicy,
    confirm_destructive,
    execute_mutation,
    fail_interaction,
)


def test_confirmation_accepts_after_showing_preview():
    policy = InteractionPolicy(force=False, no_input=False)

    with patch("pygog.interaction.typer.confirm", return_value=True) as confirm:
        assert policy.authorize("send email", "to recipient@example.com") is True

    confirm.assert_called_once()
    assert "send email" in confirm.call_args.args[0]
    assert "recipient@example.com" in confirm.call_args.args[0]


def test_confirmation_decline_exits_without_authorizing():
    policy = InteractionPolicy(force=False, no_input=False)

    with patch("pygog.interaction.typer.confirm", return_value=False):
        with pytest.raises(typer.Exit) as exc_info:
            policy.authorize("delete file", "file-id")

    assert exc_info.value.exit_code == 0


def test_force_skips_confirmation():
    policy = InteractionPolicy(force=True, no_input=False)

    with patch("pygog.interaction.typer.confirm") as confirm:
        assert policy.authorize("delete file", "file-id") is True

    confirm.assert_not_called()


def test_local_force_skips_confirmation():
    policy = InteractionPolicy(force=False, no_input=False)

    with patch("pygog.interaction.typer.confirm") as confirm:
        assert policy.authorize("delete file", "file-id", local_force=True) is True

    confirm.assert_not_called()


def test_no_input_fails_without_prompt():
    policy = InteractionPolicy(force=False, no_input=True)

    with patch("pygog.interaction.typer.confirm") as confirm:
        with pytest.raises(typer.Exit) as exc_info:
            policy.authorize("send email", "to recipient@example.com")

    assert exc_info.value.exit_code == 1
    confirm.assert_not_called()


def test_plain_output_fails_confirmation_without_writing_prompt_to_stdout(capsys):
    policy = InteractionPolicy(force=False, no_input=False, plain_output=True)

    with patch("pygog.interaction.typer.confirm") as confirm:
        with pytest.raises(typer.Exit) as exc_info:
            policy.authorize("send email", "to recipient@example.com")

    captured = capsys.readouterr()
    assert exc_info.value.exit_code == 1
    assert captured.out == ""
    assert "Confirmation required" in captured.err
    confirm.assert_not_called()


def test_dry_run_skips_confirmation():
    policy = InteractionPolicy(force=False, no_input=True)

    with patch("pygog.interaction.typer.confirm") as confirm:
        assert policy.authorize("send email", "to recipient@example.com", dry_run=True) is False

    confirm.assert_not_called()


def test_confirm_destructive_reads_global_state():
    state.force = True
    with patch("pygog.interaction.typer.confirm") as confirm:
        assert confirm_destructive("delete", "target") is True
    confirm.assert_not_called()


def test_json_interaction_error_is_only_on_stdout(capsys):
    state.json_output = True

    with pytest.raises(typer.Exit):
        fail_interaction(
            "Confirmation required; use --force or --dry-run.", code="confirmation_required"
        )

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "error": {
            "code": "confirmation_required",
            "message": "Confirmation required; use --force or --dry-run.",
        }
    }
    assert captured.err == ""


def test_json_mutation_error_is_only_on_stdout(capsys):
    with pytest.raises(typer.Exit):
        execute_mutation(
            lambda: (_ for _ in ()).throw(RuntimeError("offline")),
            action="send email",
            json_output=True,
        )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["error"]["code"] == "mutation_failed"
    assert "send email failed" in payload["error"]["message"]
    assert captured.err == ""


def test_mutation_preserves_safe_local_validation_message(capsys):
    message = "Attendee response must be accepted, declined, or tentative"

    with pytest.raises(typer.Exit) as exc_info:
        execute_mutation(
            lambda: (_ for _ in ()).throw(ValueError(message)),
            action="respond to calendar event",
            json_output=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.exit_code == ValidationError.exit_code
    assert json.loads(captured.out) == {"error": {"code": "validation_error", "message": message}}
    assert captured.err == ""


@pytest.mark.parametrize(
    "message",
    [
        "No account specified. Use --account or set GOG_ACCOUNT.",
        "No credentials found for 'user@example.com'. Run: pygog auth add user@example.com",
    ],
)
def test_mutation_preserves_missing_authentication_guidance(capsys, message):
    with pytest.raises(typer.Exit):
        execute_mutation(
            lambda: (_ for _ in ()).throw(ValueError(message)),
            action="send email",
        )

    captured = capsys.readouterr()
    assert message in captured.err
    assert "send email failed" not in captured.err


def test_mutation_preserves_typed_pygog_error(capsys):
    error = ConfigurationError("System keyring is unavailable; configure Secret Service.")

    with pytest.raises(typer.Exit) as exc_info:
        execute_mutation(
            lambda: (_ for _ in ()).throw(error),
            action="remove authorized account",
            json_output=True,
        )

    captured = capsys.readouterr()
    assert exc_info.value.exit_code == error.exit_code
    assert json.loads(captured.out) == {
        "error": {"code": "configuration_error", "message": error.message}
    }
    assert captured.err == ""


@pytest.mark.parametrize("json_output, plain_output", [(True, False), (False, True)])
def test_machine_mutation_error_does_not_expose_exception_details(
    capsys,
    json_output,
    plain_output,
):
    with pytest.raises(typer.Exit):
        execute_mutation(
            lambda: (_ for _ in ()).throw(RuntimeError("SECRET_BODY")),
            action="send email",
            json_output=json_output,
            plain_output=plain_output,
        )

    captured = capsys.readouterr()
    assert "SECRET_BODY" not in captured.out
    assert "SECRET_BODY" not in captured.err


def test_verbose_mutation_error_keeps_raw_detail_on_stderr_only(capsys):
    state.verbose = True

    with pytest.raises(typer.Exit):
        execute_mutation(
            lambda: (_ for _ in ()).throw(RuntimeError("SECRET_BODY")),
            action="send email",
            json_output=True,
        )

    captured = capsys.readouterr()
    assert "SECRET_BODY" not in captured.out
    assert "SECRET_BODY" in captured.err
