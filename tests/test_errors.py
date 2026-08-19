from __future__ import annotations

import json

import click
import pytest
import typer
from typer.core import TyperGroup
from typer.main import get_current_context
from typer.testing import CliRunner

from pygog import cli
from pygog.context import CliContext, bind_context
from pygog.errors import (
    EXIT_CODES,
    AuthenticationError,
    ConfigurationError,
    NetworkError,
    NotFoundError,
    PermissionError,
    PygogError,
    RateLimitError,
    ValidationError,
    error_payload,
)

ERROR_CASES = (
    (ConfigurationError, "configuration_error"),
    (AuthenticationError, "authentication_error"),
    (PermissionError, "permission_error"),
    (RateLimitError, "rate_limit_error"),
    (ValidationError, "validation_error"),
    (NetworkError, "network_error"),
    (NotFoundError, "not_found_error"),
)


def boundary_app(error: PygogError, *, json_output: bool = False, verbose: bool = False):
    app = typer.Typer(cls=cli.ErrorBoundaryGroup)

    @app.callback()
    def root() -> None:
        context = get_current_context()
        bind_context(
            context,
            CliContext(json_output=json_output, verbose=verbose),
        )

    @app.command()
    def fail() -> None:
        raise error

    return app


@pytest.mark.parametrize(("error_type", "code"), ERROR_CASES)
def test_typed_errors_have_stable_codes_and_exit_codes(error_type, code):
    error = error_type("operation failed")

    assert isinstance(error, PygogError)
    assert error.code == code
    assert error.exit_code == EXIT_CODES[code]
    assert error.exit_code > 0


def test_error_payload_is_stable_and_does_not_expose_exception_class():
    error = ValidationError("invalid account", details={"field": "account"})

    assert error_payload(error) == {
        "error": {
            "code": "validation_error",
            "message": "invalid account",
            "details": {"field": "account"},
        }
    }


@pytest.mark.parametrize(("error_type", "code"), ERROR_CASES)
def test_typed_error_boundary_returns_json_and_human_diagnostic(error_type, code):
    result = CliRunner().invoke(
        boundary_app(error_type("provider details"), json_output=True),
        ["fail"],
    )

    assert result.exit_code == EXIT_CODES[code]
    assert json.loads(result.stdout) == {"error": {"code": code, "message": "provider details"}}
    assert "provider details" in result.stderr
    assert "Traceback" not in result.stderr


def test_typed_error_boundary_keeps_human_output_off_stdout():
    result = CliRunner().invoke(
        boundary_app(NetworkError("offline")),
        ["fail"],
    )

    assert result.exit_code == EXIT_CODES["network_error"]
    assert result.stdout == ""
    assert "Error [network_error]: offline" in result.stderr
    assert "Traceback" not in result.stderr


def test_verbose_typed_error_boundary_adds_traceback_to_stderr_only():
    result = CliRunner().invoke(
        boundary_app(NetworkError("offline"), verbose=True),
        ["fail"],
    )

    assert result.exit_code == EXIT_CODES["network_error"]
    assert result.stdout == ""
    assert "Error [network_error]: offline" in result.stderr
    assert "Traceback" in result.stderr


def test_error_boundary_does_not_convert_keyboard_interrupt():
    original_invoke = TyperGroup.invoke

    def raise_interrupt(self, context):
        raise KeyboardInterrupt()

    TyperGroup.invoke = raise_interrupt
    try:
        with pytest.raises(KeyboardInterrupt):
            cli.ErrorBoundaryGroup().invoke(click.Context(click.Command("test")))
    finally:
        TyperGroup.invoke = original_invoke
