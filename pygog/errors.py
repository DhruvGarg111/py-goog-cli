"""Stable, typed CLI errors and rendering helpers."""

from __future__ import annotations

import sys
import traceback
from collections.abc import Mapping
from typing import Any, TextIO

# These values are part of the scripting contract.  Keep them explicit rather
# than deriving them from exception class order or provider status codes.
EXIT_CODES: dict[str, int] = {
    "configuration_error": 2,
    "authentication_error": 3,
    "permission_error": 4,
    "rate_limit_error": 5,
    "validation_error": 6,
    "network_error": 7,
    "not_found_error": 8,
}


class PygogError(Exception):
    """Base class for errors safe to expose at the CLI boundary."""

    code = "error"
    exit_code = 1

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None):
        self.message = str(message)
        self.details = dict(details) if details is not None else None
        super().__init__(self.message)


class ConfigurationError(PygogError):
    """The local configuration is missing or invalid."""

    code = "configuration_error"
    exit_code = EXIT_CODES[code]


class AuthenticationError(PygogError):
    """Credentials are absent, invalid, or no longer accepted."""

    code = "authentication_error"
    exit_code = EXIT_CODES[code]


class PermissionError(PygogError):
    """The authenticated principal cannot perform the operation."""

    code = "permission_error"
    exit_code = EXIT_CODES[code]


class RateLimitError(PygogError):
    """The provider rejected the request because a quota was exceeded."""

    code = "rate_limit_error"
    exit_code = EXIT_CODES[code]


class ValidationError(PygogError):
    """User input or a local command argument is invalid."""

    code = "validation_error"
    exit_code = EXIT_CODES[code]


class NetworkError(PygogError):
    """A provider request could not be completed due to connectivity."""

    code = "network_error"
    exit_code = EXIT_CODES[code]


class NotFoundError(PygogError):
    """The requested provider resource does not exist."""

    code = "not_found_error"
    exit_code = EXIT_CODES[code]


# A neutral alias is convenient for adapters that do not want to depend on a
# particular error category.  Keep the historical-looking spelling public.
CliError = PygogError


def error_payload(error: PygogError) -> dict[str, Any]:
    """Return the stable machine-readable representation of *error*."""
    result: dict[str, Any] = {
        "code": error.code,
        "message": error.message,
    }
    if error.details is not None:
        result["details"] = dict(error.details)
    return {"error": result}


def emit_error(
    error: PygogError,
    *,
    json_output: bool = False,
    verbose: bool = False,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Write one stable diagnostic and return its process exit code.

    JSON is intentionally written only to stdout.  A short human diagnostic
    is always written to stderr so shell pipelines remain safe; verbose mode
    adds the traceback to stderr and never to the machine-readable response.
    """
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    if json_output:
        import json

        print(json.dumps(error_payload(error), ensure_ascii=False), file=stdout)

    print(f"Error [{error.code}]: {error.message}", file=stderr)
    if verbose:
        traceback.print_exception(type(error), error, error.__traceback__, file=stderr)
    return error.exit_code


# Naming used by callers that think in terms of rendering rather than emitting.
render_error = emit_error


__all__ = [
    "EXIT_CODES",
    "PygogError",
    "CliError",
    "ConfigurationError",
    "AuthenticationError",
    "PermissionError",
    "RateLimitError",
    "ValidationError",
    "NetworkError",
    "NotFoundError",
    "error_payload",
    "emit_error",
    "render_error",
]
