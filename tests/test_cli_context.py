from __future__ import annotations

from dataclasses import is_dataclass
from importlib import import_module
from unittest.mock import patch

import click
import pytest
from typer.testing import CliRunner

from pygog import cli
from pygog.cli import state
from pygog.commands import auth as auth_commands
from pygog.config import Config
from pygog.context import CliContext, bind_context, get_context
from pygog.errors import ValidationError
from pygog.services.gmail import GmailService

COMMAND_MODULES = (
    "pygog.commands.gmail",
    "pygog.commands.calendar",
    "pygog.commands.drive",
    "pygog.commands.tasks",
)


@pytest.fixture(autouse=True)
def reset_cli_state(monkeypatch):
    monkeypatch.delenv("GOG_CLIENT", raising=False)
    original = {
        "account": state.account,
        "client": state.client,
        "json_output": state.json_output,
        "plain_output": state.plain_output,
        "color": state.color,
        "verbose": state.verbose,
        "force": state.force,
        "no_input": state.no_input,
    }
    state.account = None
    state.client = None
    state.json_output = False
    state.plain_output = False
    state.color = "auto"
    state.verbose = False
    state.force = False
    state.no_input = False
    yield
    for name, value in original.items():
        setattr(state, name, value)
    cli._configure_consoles("auto")


def make_config(**data) -> Config:
    config = Config()
    config._data = data
    config._loaded = True
    return config


def invoke_cli(
    config: Config,
    *,
    account: str | None,
    client: str | None,
    color: str | None = "auto",
) -> None:
    with patch("pygog.cli.get_config", return_value=config):
        cli.main(
            account=account,
            client=client,
            json_output=False,
            plain_output=False,
            color=color,
            verbose=False,
            force=False,
            no_input=False,
            version=False,
        )


def construct_command_service(
    module_name: str,
    config: Config,
    *,
    account: str | None,
    client: str | None,
):
    module = import_module(module_name)
    with (
        patch("pygog.cli.get_config", return_value=config),
        patch("pygog.services.base.get_config", return_value=config),
        patch("pygog.services.base.GoogleAuthClient") as auth_client,
    ):
        invoke_cli(config, account=account, client=client)
        service = module.get_service()
    return service, auth_client


def test_cli_keeps_client_override_none_when_not_selected():
    config = make_config(default_account="work@example.com", default_client="configured-client")

    invoke_cli(config, account=None, client=None)

    assert state.account == "work@example.com"
    assert state.client is None


def test_repeated_cli_callbacks_do_not_leak_client_override():
    config = make_config(default_account="work@example.com", default_client="configured-client")

    invoke_cli(config, account=None, client="first-client")
    assert state.client == "first-client"

    invoke_cli(config, account=None, client=None)

    assert state.client is None


def test_auth_client_uses_configured_client_without_override():
    config = make_config(default_client="configured-client")

    with (
        patch("pygog.commands.auth.get_config", return_value=config),
        patch("pygog.commands.auth.GoogleAuthClient") as auth_client,
    ):
        auth_commands._get_auth_client(None)

    auth_client.assert_called_once_with("configured-client")


def test_auth_client_uses_explicit_client_override():
    config = make_config(default_client="configured-client")

    with (
        patch("pygog.commands.auth.get_config", return_value=config),
        patch("pygog.commands.auth.GoogleAuthClient") as auth_client,
    ):
        auth_commands._get_auth_client("explicit-client")

    auth_client.assert_called_once_with("explicit-client")


def test_auth_credentials_uses_global_client_override(tmp_path):
    config = make_config(default_client="configured-client")
    state.client = "global-client"
    credentials_path = tmp_path / "client.json"

    with (
        patch("pygog.commands.auth.get_config", return_value=config),
        patch("pygog.commands.auth.CredentialsManager") as manager,
    ):
        auth_commands.credentials_cmd(
            path=credentials_path,
            domain=None,
            list_creds=False,
            client=None,
        )

    manager.assert_called_once_with("global-client")
    manager.return_value.store.assert_called_once_with(credentials_path, domain=None)


def test_auth_credentials_uses_configured_client_fallback(tmp_path):
    config = make_config(default_client="configured-client")
    credentials_path = tmp_path / "client.json"

    with (
        patch("pygog.commands.auth.get_config", return_value=config),
        patch("pygog.commands.auth.CredentialsManager") as manager,
    ):
        auth_commands.credentials_cmd(
            path=credentials_path,
            domain=None,
            list_creds=False,
            client=None,
        )

    manager.assert_called_once_with("configured-client")
    manager.return_value.store.assert_called_once_with(credentials_path, domain=None)


def test_auth_status_honors_global_client_override():
    config = make_config(
        default_account="work@example.com",
        account_clients={"work@example.com": "account-client"},
    )
    state.client = "global-client"

    with (
        patch("pygog.commands.auth.get_config", return_value=config),
        patch("pygog.commands.auth.GoogleAuthClient") as auth_client,
    ):
        auth_client.return_value.check_token.return_value = {"valid": False}
        auth_commands.status_cmd(account=None)

    auth_client.assert_called_once_with("global-client")
    auth_client.return_value.check_token.assert_called_once_with("work@example.com")


def test_auth_status_uses_account_client_mapping_without_global_override():
    config = make_config(
        default_account="work@example.com",
        account_clients={"work@example.com": "account-client"},
    )

    with (
        patch("pygog.commands.auth.get_config", return_value=config),
        patch("pygog.commands.auth.GoogleAuthClient") as auth_client,
    ):
        auth_client.return_value.check_token.return_value = {"valid": False}
        auth_commands.status_cmd(account=None)

    auth_client.assert_called_once_with("account-client")
    auth_client.return_value.check_token.assert_called_once_with("work@example.com")


@pytest.mark.parametrize("module_name", COMMAND_MODULES)
def test_command_get_service_routes_exact_account_client(module_name: str):
    config = make_config(
        account_aliases={"work": "work@example.com"},
        account_clients={"work@example.com": "work-client"},
        client_domains={"example.com": "domain-client"},
        default_client="configured-client",
    )

    service, auth_client = construct_command_service(
        module_name,
        config,
        account="work",
        client=None,
    )

    assert service.account == "work@example.com"
    auth_client.assert_called_once_with("work-client")


@pytest.mark.parametrize("module_name", COMMAND_MODULES)
def test_command_get_service_routes_domain_client(module_name: str):
    config = make_config(
        account_aliases={"personal": "personal@example.net"},
        account_clients={},
        client_domains={"example.net": "personal-client"},
        default_client="configured-client",
    )

    service, auth_client = construct_command_service(
        module_name,
        config,
        account="personal",
        client=None,
    )

    assert service.account == "personal@example.net"
    auth_client.assert_called_once_with("personal-client")


def test_service_routes_default_account_alias_to_account_client():
    config = make_config(
        default_account="work",
        account_aliases={"work": "work@example.com"},
        account_clients={"work@example.com": "work-client"},
        default_client="configured-client",
    )

    with (
        patch("pygog.services.base.get_config", return_value=config),
        patch("pygog.services.base.GoogleAuthClient") as auth_client,
    ):
        service = GmailService(account=None)

    assert service.account == "work@example.com"
    auth_client.assert_called_once_with("work-client")


def test_service_routes_environment_account_alias_to_domain_client():
    config = make_config(
        account_aliases={"personal": "personal@example.net"},
        client_domains={"example.net": "personal-client"},
        default_client="configured-client",
    )

    with (
        patch.dict("os.environ", {"GOG_ACCOUNT": "personal"}, clear=True),
        patch("pygog.services.base.get_config", return_value=config),
        patch("pygog.services.base.GoogleAuthClient") as auth_client,
    ):
        service = GmailService(account=None)

    assert service.account == "personal@example.net"
    auth_client.assert_called_once_with("personal-client")


@pytest.mark.parametrize(
    ("account", "client", "config_data", "expected_client"),
    [
        (
            "work@example.com",
            "explicit-client",
            {
                "account_clients": {"work@example.com": "account-client"},
                "client_domains": {"example.com": "domain-client"},
                "default_client": "configured-client",
            },
            "explicit-client",
        ),
        (
            "work@example.com",
            None,
            {
                "account_clients": {"work@example.com": "account-client"},
                "client_domains": {"example.com": "domain-client"},
                "default_client": "configured-client",
            },
            "account-client",
        ),
        (
            "other@example.com",
            None,
            {
                "account_clients": {},
                "client_domains": {"example.com": "domain-client"},
                "default_client": "configured-client",
            },
            "domain-client",
        ),
        (
            "other@outside.test",
            None,
            {"account_clients": {}, "client_domains": {}, "default_client": "configured-client"},
            "configured-client",
        ),
        (
            "other@outside.test",
            None,
            {"account_clients": {}, "client_domains": {}},
            "default",
        ),
    ],
)
def test_service_client_routing_precedence(
    account: str,
    client: str | None,
    config_data: dict,
    expected_client: str,
):
    config = make_config(**config_data)

    with (
        patch("pygog.services.base.get_config", return_value=config),
        patch("pygog.services.base.GoogleAuthClient") as auth_client,
    ):
        service = GmailService(account=account, client=client)

    assert service.account == account
    auth_client.assert_called_once_with(expected_client)


def test_gog_client_environment_override_precedes_account_mappings():
    config = make_config(
        account_clients={"work@example.com": "account-client"},
        client_domains={"example.com": "domain-client"},
        default_client="configured-client",
    )

    with (
        patch.dict("os.environ", {"GOG_CLIENT": "environment-client"}, clear=True),
        patch("pygog.services.base.get_config", return_value=config),
        patch("pygog.services.base.GoogleAuthClient") as auth_client,
    ):
        service = GmailService(account="work@example.com")

    assert service.account == "work@example.com"
    auth_client.assert_called_once_with("environment-client")


def test_cli_context_is_typed_and_state_alias_remains_compatible():
    assert is_dataclass(CliContext)
    assert cli.State is CliContext
    assert isinstance(state, CliContext)


def test_cli_context_bridges_through_click_context_obj():
    click_context = click.Context(click.Command("test"))

    context = bind_context(click_context, CliContext(account="user@example.com"))

    assert click_context.obj is context
    assert get_context(click_context) is context
    assert context.account == "user@example.com"


def test_json_and_plain_are_mutually_exclusive():
    result = CliRunner().invoke(cli.app, ["--json", "--plain", "time", "now"])

    assert result.exit_code == ValidationError.exit_code
    assert "mutually exclusive" in result.stderr


def test_configured_color_mode_is_used_when_cli_color_is_omitted():
    config = make_config(color="never")

    invoke_cli(config, account=None, client=None, color=None)

    assert state.color == "never"
    assert cli.console.no_color is True
    assert cli.err_console.no_color is True


def test_explicit_color_mode_overrides_configured_color_mode():
    config = make_config(color="never")

    invoke_cli(config, account=None, client=None, color="always")

    assert state.color == "always"
    assert cli.console.is_terminal is True
    assert cli.err_console.is_terminal is True


def test_global_color_mode_applies_to_real_command_output():
    config = make_config(color="auto")

    with (
        patch("pygog.cli.get_config", return_value=config),
        patch("pygog.commands.time_cmd.get_config", return_value=config),
    ):
        always = CliRunner().invoke(
            cli.app,
            ["--color", "always", "time", "now", "--timezone", "Invalid/Zone"],
        )
        never = CliRunner().invoke(
            cli.app,
            ["--color", "never", "time", "now", "--timezone", "Invalid/Zone"],
        )

    assert always.exit_code == 1
    assert "\x1b[31mUnknown timezone:\x1b[0m" in always.stdout
    assert never.exit_code == 1
    assert "\x1b[" not in never.stdout
    assert "Unknown timezone: Invalid/Zone" in never.stdout


def test_global_color_mode_rebinds_agent_core_consoles():
    from pygog.agent import core as agent_core

    cli._configure_consoles("never")

    assert agent_core.console.no_color is True
    assert agent_core.err_console.no_color is True
