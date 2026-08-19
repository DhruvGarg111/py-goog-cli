"""Explicit trust-boundary controls for the natural-language agent.

The policy in this module is intentionally independent from model output.  Tool
results are data crossing into the model context; they never get to mutate an
:class:`AgentPolicy` or authorize a write.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class PolicyError(Exception):
    """A safe, structured error raised when an agent action is not authorized."""

    def __init__(self, code: str, message: str, *, tool: str | None = None):
        self.code = code
        self.message = message
        self.tool = tool
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        """Return a machine-readable error without including tool arguments."""
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.tool is not None:
            result["tool"] = self.tool
        return result


@dataclass(frozen=True)
class AgentPolicy:
    """Authorization state for one agent run.

    ``allow_write`` is an explicit capability granted by the local CLI user.
    Even with that capability, destructive tools require ``confirmed=True`` at
    the point of execution.  Model messages and tool results are not inputs to
    this object.
    """

    allow_write: bool = False
    allowed_tools: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.allowed_tools is not None and not isinstance(self.allowed_tools, frozenset):
            object.__setattr__(self, "allowed_tools", frozenset(self.allowed_tools))

    def is_exposed(self, tool_name: str, *, destructive: bool) -> bool:
        """Return whether a tool may be advertised to the model."""
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            return False
        return not destructive or self.allow_write

    def authorize(
        self,
        tool_name: str,
        *,
        destructive: bool,
        confirmed: bool = False,
    ) -> None:
        """Authorize one tool invocation using only local policy state."""
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            raise PolicyError(
                "tool_not_allowed",
                "The tool is not enabled by the local tool allowlist.",
                tool=tool_name,
            )
        if destructive and not self.allow_write:
            raise PolicyError(
                "write_not_allowed",
                "Write tools require the explicit --allow-write option.",
                tool=tool_name,
            )
        if destructive and not confirmed:
            raise PolicyError(
                "confirmation_required",
                "A local confirmation is required before this write action.",
                tool=tool_name,
            )


def parse_tool_allowlist(value: str | Iterable[str] | None) -> frozenset[str] | None:
    """Parse a comma-separated or iterable tool allowlist.

    ``None`` means no name restriction.  An empty string intentionally means
    an empty allowlist, which is safer than treating a user-supplied value as
    unrestricted.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return frozenset(item.strip() for item in value.split(",") if item.strip())
    return frozenset(str(item).strip() for item in value if str(item).strip())


def wrap_tool_result(tool_name: str, result: Any) -> dict[str, Any]:
    """Mark a retrieved result as untrusted data before it enters the LLM context."""
    return {
        "trust": "untrusted",
        "source": "tool_result",
        "tool": tool_name,
        "data": result,
    }


_SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "auth_token",
    "client_secret",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
)

_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:api[_-]?key|authorization|auth[_-]?token|client[_-]?secret|"
    r"password|private[_-]?key|refresh[_-]?token|secret|token)\b\s*[:=]\s*)"
    r"([^\s,;]+)"
)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SECRET_KEY_PARTS)


def _redact_text(value: str) -> str:
    return _SECRET_ASSIGNMENT_RE.sub(r"\1[REDACTED]", value)


def safe_for_log(value: Any, *, key: object | None = None) -> Any:
    """Copy a value for diagnostics while redacting secret-shaped fields."""
    if key is not None and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, Mapping):
        return {str(k): safe_for_log(v, key=k) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [safe_for_log(item) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [safe_for_log(item) for item in value]
    return value


def safe_error_message(error: BaseException | object) -> str:
    """Return an exception/result message suitable for console output."""
    if isinstance(error, PolicyError):
        return error.message
    if isinstance(error, Mapping):
        return str(safe_for_log(error))
    return str(safe_for_log(str(error)))
