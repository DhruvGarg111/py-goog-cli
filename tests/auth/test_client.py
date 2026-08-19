"""Offline tests for Google OAuth credential lifecycle behavior."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.oauth2.credentials import Credentials

import pygog.auth.client as client_module
from pygog.auth.client import AuthenticationError, GoogleAuthClient
from pygog.auth.keyring import KeyringStorageError


class FakeKeyring:
    def __init__(self, token_data=None):
        self.token_data = token_data
        self.stored = []
        self.added = []
        self.get_calls = []
        self.delete_calls = []

    def get_token(self, account):
        self.get_calls.append(account)
        return self.token_data

    def store_token(self, account, token_data):
        self.stored.append((account, token_data))

    def add_account_to_list(self, account):
        self.added.append(account)

    def delete_token(self, account):
        self.delete_calls.append(account)
        if self.token_data is None:
            return False
        self.token_data = None
        return True

    def remove_account_from_list(self, account):
        return None

    def list_accounts(self):
        return ["user@example.com"] if self.token_data else []


def _client(monkeypatch, keyring):
    manager = Mock()
    manager.get_client_config.return_value = {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    monkeypatch.setattr(client_module, "CredentialsManager", lambda client: manager)
    monkeypatch.setattr(client_module, "KeyringStorage", lambda client: keyring)
    monkeypatch.setattr(
        client_module,
        "ServiceAccountStorage",
        lambda: Mock(get_key=lambda account: None),
    )
    return GoogleAuthClient("default")


def _flow(monkeypatch, credentials, calls):
    flow = SimpleNamespace()

    def run_local_server(**kwargs):
        calls.append(kwargs)
        return credentials

    flow.run_local_server = run_local_server
    monkeypatch.setattr(
        client_module.InstalledAppFlow,
        "from_client_config",
        Mock(return_value=flow),
    )


def _credentials(
    *,
    refresh_token="refresh-token",
    expiry=None,
    id_token="id-token",
    client_id="client-id",
):
    return Credentials(
        token="access-token",
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret="client-secret",
        scopes=["scope-a"],
        expiry=expiry,
        id_token=id_token,
    )


def test_authorize_serializes_expiry_and_requests_verified_identity(monkeypatch):
    keyring = FakeKeyring()
    auth = _client(monkeypatch, keyring)
    credentials = _credentials(
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    calls = []
    _flow(monkeypatch, credentials, calls)
    monkeypatch.setattr(
        client_module,
        "verify_oauth2_token",
        Mock(return_value={"email": "user@example.com", "email_verified": True}),
        raising=False,
    )

    result = auth.authorize("user@example.com", services=["gmail"])

    assert result is credentials
    flow_factory = client_module.InstalledAppFlow.from_client_config
    assert "openid" in flow_factory.call_args.kwargs["scopes"]
    assert "email" in flow_factory.call_args.kwargs["scopes"]
    stored_account, token_data = keyring.stored[0]
    assert stored_account == "user@example.com"
    assert token_data["expiry"].endswith("Z")
    assert datetime.fromisoformat(token_data["expiry"].rstrip("Z")).tzinfo is None
    assert token_data["refresh_token"] == "refresh-token"


def test_authorize_uses_trusted_configured_client_id_for_audience(monkeypatch):
    keyring = FakeKeyring()
    auth = _client(monkeypatch, keyring)
    credentials = _credentials(
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        client_id="untrusted-credential-client",
    )
    calls = []
    _flow(monkeypatch, credentials, calls)
    verify = Mock(return_value={"email": "user@example.com", "email_verified": True})
    monkeypatch.setattr(client_module, "verify_oauth2_token", verify, raising=False)

    auth.authorize("user@example.com", services=["gmail"])

    assert verify.call_args.kwargs["audience"] == "client-id"
    assert keyring.stored[0][1]["client_id"] == "client-id"


def test_authorize_fails_closed_when_configured_client_id_is_missing(monkeypatch):
    keyring = FakeKeyring()
    auth = _client(monkeypatch, keyring)
    auth._credentials_manager.get_client_config.return_value.pop("client_id")
    credentials = _credentials(
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        client_id="untrusted-credential-client",
    )
    calls = []
    _flow(monkeypatch, credentials, calls)
    verify = Mock(return_value={"email": "user@example.com", "email_verified": True})
    monkeypatch.setattr(client_module, "verify_oauth2_token", verify, raising=False)

    with pytest.raises(AuthenticationError, match="client ID"):
        auth.authorize("user@example.com", services=["gmail"])

    verify.assert_not_called()
    assert keyring.stored == []


def test_authorize_passes_consent_prompt_only_when_requested(monkeypatch):
    for force_consent, expected in ((False, None), (True, "consent")):
        keyring = FakeKeyring()
        auth = _client(monkeypatch, keyring)
        credentials = _credentials(expiry=datetime.now(timezone.utc) + timedelta(hours=1))
        calls = []
        _flow(monkeypatch, credentials, calls)
        monkeypatch.setattr(
            client_module,
            "verify_oauth2_token",
            Mock(return_value={"email": "user@example.com", "email_verified": True}),
            raising=False,
        )

        auth.authorize("user@example.com", services=["gmail"], force_consent=force_consent)

        assert calls[0].get("prompt") == expected
        if expected is None:
            assert "prompt" not in calls[0]


def test_reauthorization_preserves_existing_refresh_token(monkeypatch):
    keyring = FakeKeyring(
        {
            "token": "old-access-token",
            "refresh_token": "long-lived-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "scopes": ["scope-a"],
            "expiry": "2030-01-01T00:00:00Z",
            "account": "USER@EXAMPLE.COM",
            "verified_account": "USER@EXAMPLE.COM",
        }
    )
    auth = _client(monkeypatch, keyring)
    credentials = _credentials(
        refresh_token=None,
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    calls = []
    _flow(monkeypatch, credentials, calls)
    monkeypatch.setattr(
        client_module,
        "verify_oauth2_token",
        Mock(return_value={"email": "user@example.com", "email_verified": True}),
        raising=False,
    )

    auth.authorize(" user@example.com ", services=["gmail"])

    assert keyring.get_calls == [" user@example.com "]
    assert keyring.stored[0][1]["refresh_token"] == "long-lived-refresh-token"


def test_reauthorization_does_not_preserve_refresh_token_for_mismatched_client(monkeypatch):
    keyring = FakeKeyring(
        {
            "token": "old-access-token",
            "refresh_token": "attacker-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "different-client-id",
            "scopes": ["scope-a"],
            "expiry": "2030-01-01T00:00:00Z",
            "verified_account": "user@example.com",
        }
    )
    auth = _client(monkeypatch, keyring)
    credentials = _credentials(
        refresh_token=None,
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    calls = []
    _flow(monkeypatch, credentials, calls)
    monkeypatch.setattr(
        client_module,
        "verify_oauth2_token",
        Mock(return_value={"email": "user@example.com", "email_verified": True}),
        raising=False,
    )

    auth.authorize("user@example.com", services=["gmail"])

    assert keyring.stored[0][1]["refresh_token"] is None


def test_reauthorization_does_not_preserve_refresh_token_for_mismatched_account(monkeypatch):
    keyring = FakeKeyring(
        {
            "token": "old-access-token",
            "refresh_token": "other-account-refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id",
            "scopes": ["scope-a"],
            "expiry": "2030-01-01T00:00:00Z",
            "verified_account": "other@example.com",
        }
    )
    auth = _client(monkeypatch, keyring)
    credentials = _credentials(
        refresh_token=None,
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    calls = []
    _flow(monkeypatch, credentials, calls)
    monkeypatch.setattr(
        client_module,
        "verify_oauth2_token",
        Mock(return_value={"email": "user@example.com", "email_verified": True}),
        raising=False,
    )

    auth.authorize("user@example.com", services=["gmail"])

    assert keyring.stored[0][1]["refresh_token"] is None


def test_authorize_refuses_to_store_mismatched_authenticated_identity(monkeypatch):
    keyring = FakeKeyring()
    auth = _client(monkeypatch, keyring)
    credentials = _credentials(expiry=datetime.now(timezone.utc) + timedelta(hours=1))
    calls = []
    _flow(monkeypatch, credentials, calls)
    monkeypatch.setattr(
        client_module,
        "verify_oauth2_token",
        Mock(return_value={"email": "different@example.com", "email_verified": True}),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="different account") as exc_info:
        auth.authorize("user@example.com", services=["gmail"])

    assert exc_info.value.__class__.__name__ == "AuthenticationError"

    assert keyring.stored == []
    assert keyring.added == []


def _stored_token(expiry=None, refresh_token="refresh-token"):
    data = {
        "token": "old-access-token",
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scopes": ["scope-a"],
    }
    if expiry is not None:
        data["expiry"] = expiry
    return data


def test_get_credentials_restores_aware_expiry_refreshes_and_persists(monkeypatch):
    old_expiry = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
    keyring = FakeKeyring(_stored_token(old_expiry.isoformat(timespec="seconds") + "Z"))
    auth = _client(monkeypatch, keyring)

    def refresh(credentials, request):
        credentials.token = "new-access-token"
        credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", refresh)

    credentials = auth.get_credentials("user@example.com")

    assert credentials is not None
    assert credentials.token == "new-access-token"
    assert credentials.expiry.tzinfo is not None
    assert keyring.stored[0][1]["token"] == "new-access-token"
    assert "expiry" in keyring.stored[0][1]


def test_get_credentials_preserves_raw_account_for_legacy_keyring_lookup(monkeypatch):
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds") + "Z"
    keyring = FakeKeyring(_stored_token(expiry, refresh_token=None))
    auth = _client(monkeypatch, keyring)

    credentials = auth.get_credentials(" User@Example.COM ")

    assert credentials is not None
    assert keyring.get_calls == [" User@Example.COM "]


def test_missing_expiry_is_not_treated_as_valid(monkeypatch):
    keyring = FakeKeyring(_stored_token(expiry=None, refresh_token=None))
    auth = _client(monkeypatch, keyring)

    credentials = auth.get_credentials("user@example.com")

    assert credentials is not None
    assert credentials.valid is False
    assert auth.check_token("user@example.com")["valid"] is False


def test_missing_access_token_with_future_expiry_refreshes(monkeypatch):
    keyring = FakeKeyring(
        _stored_token(
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds") + "Z"
        )
    )
    keyring.token_data["token"] = None
    auth = _client(monkeypatch, keyring)

    def refresh(credentials, request):
        credentials.token = "new-access-token"
        credentials.expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    monkeypatch.setattr(Credentials, "refresh", refresh)

    credentials = auth.get_credentials("user@example.com")

    assert credentials.token == "new-access-token"
    assert keyring.stored[0][1]["token"] == "new-access-token"


def test_missing_access_token_without_refresh_token_remains_invalid(monkeypatch):
    keyring = FakeKeyring(
        _stored_token(
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds") + "Z",
            refresh_token=None,
        )
    )
    keyring.token_data["token"] = None
    auth = _client(monkeypatch, keyring)

    credentials = auth.get_credentials("user@example.com")

    assert credentials.valid is False
    assert auth.check_token("user@example.com")["valid"] is False
    assert keyring.stored == []


@pytest.mark.parametrize("metadata_field", ["account", "verified_account"])
def test_get_credentials_rejects_mismatched_stored_provenance(monkeypatch, metadata_field):
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds") + "Z"
    token_data = _stored_token(expiry, refresh_token=None)
    token_data[metadata_field] = "other@example.com"
    auth = _client(monkeypatch, FakeKeyring(token_data))

    with pytest.raises(AuthenticationError, match="provenance"):
        auth.get_credentials("user@example.com")


@pytest.mark.parametrize("metadata_field", ["account", "verified_account"])
def test_refresh_rejects_mismatched_stored_provenance_before_refresh(monkeypatch, metadata_field):
    expiry = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds") + "Z"
    token_data = _stored_token(expiry)
    token_data[metadata_field] = "other@example.com"
    auth = _client(monkeypatch, FakeKeyring(token_data))
    refresh = Mock()
    monkeypatch.setattr(Credentials, "refresh", refresh)

    with pytest.raises(AuthenticationError, match="provenance"):
        auth.get_credentials("user@example.com")

    refresh.assert_not_called()


def test_legacy_token_without_provenance_metadata_is_allowed(monkeypatch):
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds") + "Z"
    auth = _client(monkeypatch, FakeKeyring(_stored_token(expiry, refresh_token=None)))

    credentials = auth.get_credentials("user@example.com")

    assert credentials is not None
    assert credentials.valid is True


def test_refresh_failure_is_typed_and_guides_reauthentication(monkeypatch):
    old_expiry = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
    keyring = FakeKeyring(_stored_token(old_expiry.isoformat(timespec="seconds") + "Z"))
    auth = _client(monkeypatch, keyring)

    def refresh(credentials, request):
        raise RuntimeError("invalid_grant")

    monkeypatch.setattr(Credentials, "refresh", refresh)

    with pytest.raises(RuntimeError, match="re-authenticate") as first_error:
        auth.get_credentials("user@example.com")
    with pytest.raises(RuntimeError, match="re-authenticate") as second_error:
        auth.check_token("user@example.com")

    assert isinstance(first_error.value, client_module.AuthenticationError)
    assert isinstance(second_error.value, client_module.AuthenticationError)


def test_refresh_without_expiry_does_not_masquerade_as_valid(monkeypatch):
    old_expiry = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
    keyring = FakeKeyring(_stored_token(old_expiry.isoformat(timespec="seconds") + "Z"))
    auth = _client(monkeypatch, keyring)

    def refresh(credentials, request):
        credentials.token = "new-access-token"
        credentials.expiry = None

    monkeypatch.setattr(Credentials, "refresh", refresh)

    with pytest.raises(RuntimeError, match="expiry") as error:
        auth.get_credentials("user@example.com")

    assert isinstance(error.value, client_module.AuthenticationError)
    assert keyring.stored == []


def test_authorized_user_serialization_can_be_loaded_from_json(monkeypatch):
    source = _credentials(expiry=datetime.now(timezone.utc) + timedelta(hours=1))
    keyring = FakeKeyring(json.loads(source.to_json()))
    auth = _client(monkeypatch, keyring)

    credentials = auth.get_credentials("user@example.com")

    assert credentials.expiry.tzinfo is not None
    assert credentials.valid is True


def test_list_accounts_keeps_service_accounts_when_oauth_keyring_fails(monkeypatch):
    keyring = Mock()
    keyring.list_accounts.side_effect = KeyringStorageError("backend unavailable")
    auth = _client(monkeypatch, keyring)
    auth._service_accounts = Mock()
    auth._service_accounts.list_accounts.return_value = ["service@example.com"]
    auth._service_accounts.has_key.return_value = True

    accounts = auth.list_accounts()

    assert accounts == [
        {
            "email": "service@example.com",
            "client": "default",
            "auth_type": "service_account",
            "has_token": False,
        }
    ]


def test_remove_service_account_does_not_require_oauth_keyring(monkeypatch):
    keyring = Mock()
    keyring.delete_token.side_effect = KeyringStorageError("backend unavailable")
    auth = _client(monkeypatch, keyring)
    auth._service_accounts = Mock()
    auth._service_accounts.get_key.return_value = {"type": "service_account"}
    auth._service_accounts.delete_key.return_value = True
    auth._service_accounts.get_key.side_effect = [{"type": "service_account"}, None]

    assert auth.remove_account("service@example.com") is True
    keyring.delete_token.assert_not_called()


def test_remove_account_returns_false_when_oauth_token_is_not_found(monkeypatch):
    keyring = Mock()
    keyring.delete_token.return_value = False
    auth = _client(monkeypatch, keyring)
    auth._service_accounts = Mock()
    auth._service_accounts.get_key.return_value = None

    assert auth.remove_account("missing@example.com") is False
    keyring.remove_account_from_list.assert_not_called()


def test_remove_oauth_account_deletes_and_verifies_raw_account(monkeypatch):
    keyring = Mock()
    keyring.delete_token.return_value = True
    keyring.get_token.return_value = None
    auth = _client(monkeypatch, keyring)
    auth._service_accounts = Mock()
    auth._service_accounts.get_key.return_value = None

    assert auth.remove_account(" User@Example.COM ") is True

    keyring.delete_token.assert_called_once_with(" User@Example.COM ")
    keyring.get_token.assert_called_once_with(" User@Example.COM ")
    keyring.remove_account_from_list.assert_called_once_with("user@example.com")


def test_remove_account_does_not_claim_success_if_oauth_credentials_remain(monkeypatch):
    keyring = Mock()
    keyring.delete_token.return_value = True
    keyring.get_token.return_value = {"token": "still-present"}
    auth = _client(monkeypatch, keyring)
    auth._service_accounts = Mock()
    auth._service_accounts.get_key.return_value = None

    assert auth.remove_account("user@example.com") is False
    keyring.remove_account_from_list.assert_not_called()


def test_default_scopes_include_only_implemented_services():
    assert set(client_module.get_scopes_for_services()) == {
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.settings.basic",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/tasks",
    }


def test_user_and_all_expand_to_the_same_default_services():
    default_scopes = client_module.get_scopes_for_services()

    assert client_module.get_scopes_for_services(["user"]) == default_scopes
    assert client_module.get_scopes_for_services(["all"]) == default_scopes


def test_unknown_service_is_rejected():
    with pytest.raises(ValueError, match="Unknown service"):
        client_module.get_scopes_for_services(["not-a-google-service"])


def test_readonly_gmail_excludes_settings_scope():
    assert client_module.get_scopes_for_services(["gmail"], readonly=True) == [
        "https://www.googleapis.com/auth/gmail.readonly",
    ]


def test_readonly_supported_services_use_readonly_scopes():
    assert set(
        client_module.get_scopes_for_services(["calendar", "drive", "tasks"], readonly=True)
    ) == {
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/tasks.readonly",
    }


@pytest.mark.parametrize("service", ["contacts", "people"])
def test_readonly_unsupported_service_is_rejected(service):
    with pytest.raises(ValueError, match="read-only scopes"):
        client_module.get_scopes_for_services([service], readonly=True)
