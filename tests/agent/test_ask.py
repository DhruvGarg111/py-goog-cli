from types import SimpleNamespace
from unittest.mock import patch

from pygog.commands import ask


def test_ask_passes_explicit_write_capability_and_tool_allowlist():
    state = SimpleNamespace(account="user@example.com", verbose=False)

    with (
        patch("pygog.cli.state", state),
        patch("pygog.agent.core.run_agent", return_value="done") as run_agent,
    ):
        ask.ask_cmd(
            query="send the report",
            yes=True,
            model="fake",
            allow_write=True,
            tools="gmail_send,drive_search",
        )

    run_agent.assert_called_once_with(
        query="send the report",
        account="user@example.com",
        auto_confirm=False,
        model="fake",
        allow_write=True,
        allowed_tools="gmail_send,drive_search",
    )
