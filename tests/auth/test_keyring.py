"""Offline tests for keyring storage error boundaries."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from keyring.errors import KeyringError, PasswordDeleteError

import pygog.auth.keyring as keyring_module
from pygog.auth.keyring import (
    KeyringDataError,
    KeyringStorage,
    KeyringStorageError,
    ServiceAccountStorage,
    configure_keyring_backend,
)
from pygog.errors import ConfigurationError, PygogError


@pytest.fixture(autouse=True)
def _mock_keyring_reads(monkeypatch):
    """Keep every keyring test independent of the host's configured backend."""
    monkeypatch.setattr(keyring_module.keyring, "get_password", Mock(return_value=None))


def test_missing_account_is_distinct_from_corrupt_data(monkeypatch):
    monkeypatch.setattr(keyring_module.keyring, "get_password", Mock(return_value=None))

    storage = KeyringStorage("default")

    assert storage.get_token("missing@example.com") is None

    monkeypatch.setattr(keyring_module.keyring, "get_password", Mock(return_value="not-json"))
    with pytest.raises(RuntimeError) as error:
        storage.get_token("corrupt@example.com")
    assert error.value.__class__.__name__ == "KeyringDataError"


def test_keyring_backend_failure_is_typed(monkeypatch):
    monkeypatch.setattr(
        keyring_module.keyring,
        "get_password",
        Mock(side_effect=KeyringError("backend unavailable")),
    )

    storage = KeyringStorage("default")

    with pytest.raises(RuntimeError, match="backend unavailable") as error:
        storage.get_token("user@example.com")
    assert error.value.__class__.__name__ == "KeyringStorageError"


def test_keyring_storage_errors_are_safe_configuration_errors():
    error = KeyringStorageError("System keyring is unavailable")

    assert isinstance(error, PygogError)
    assert isinstance(error, ConfigurationError)
    assert error.code == "configuration_error"


def test_auto_backend_discovery_failure_is_typed_and_actionable(monkeypatch):
    monkeypatch.setattr(
        keyring_module.keyring,
        "get_keyring",
        Mock(side_effect=RuntimeError("No recommended backend was available")),
    )

    with pytest.raises(KeyringStorageError) as error:
        configure_keyring_backend("auto")

    assert "supported system keyring backend" in error.value.message
    assert "Linux" in error.value.message


def test_store_backend_failure_is_typed(monkeypatch):
    monkeypatch.setattr(
        keyring_module.keyring,
        "set_password",
        Mock(side_effect=KeyringError("backend unavailable")),
    )

    storage = KeyringStorage("default")

    with pytest.raises(RuntimeError, match="backend unavailable") as error:
        storage.store_token("user@example.com", {"token": "value"})
    assert error.value.__class__.__name__ == "KeyringStorageError"


def test_empty_json_object_is_rejected_as_token_data(monkeypatch):
    monkeypatch.setattr(keyring_module.keyring, "get_password", Mock(return_value="{}"))

    with pytest.raises(KeyringDataError, match="not token data"):
        KeyringStorage("default").get_token("user@example.com")


def test_non_token_json_object_is_rejected(monkeypatch):
    monkeypatch.setattr(
        keyring_module.keyring,
        "get_password",
        Mock(return_value='{"profile": "user@example.com"}'),
    )

    with pytest.raises(KeyringDataError, match="not token data"):
        KeyringStorage("default").get_token("user@example.com")


def test_token_serialization_failure_is_typed(monkeypatch):
    monkeypatch.setattr(keyring_module.keyring, "set_password", Mock())

    with pytest.raises(KeyringStorageError, match="serialize"):
        KeyringStorage("default").store_token("user@example.com", {"token": object()})


def test_missing_password_delete_is_not_found(monkeypatch):
    monkeypatch.setattr(
        keyring_module.keyring,
        "delete_password",
        Mock(side_effect=PasswordDeleteError("not found")),
    )

    assert KeyringStorage("default").delete_token("missing@example.com") is False


def test_store_token_uses_canonical_account_key(monkeypatch):
    set_password = Mock()
    monkeypatch.setattr(keyring_module.keyring, "set_password", set_password)

    KeyringStorage("default").store_token(
        " User@Example.COM ",
        {"token": "value"},
    )

    assert set_password.call_args.args[1] == "token:default:user@example.com"


def test_get_token_falls_back_to_legacy_raw_account_key(monkeypatch):
    account = " User@Example.COM "
    canonical_key = "token:default:user@example.com"
    legacy_key = f"token:default:{account}"
    values = {
        canonical_key: None,
        legacy_key: json.dumps({"token": "legacy-value"}),
    }
    get_password = Mock(side_effect=lambda service, key: values[key])
    monkeypatch.setattr(keyring_module.keyring, "get_password", get_password)

    token = KeyringStorage("default").get_token(account)

    assert token == {"token": "legacy-value"}
    assert [call.args for call in get_password.call_args_list] == [
        ("pygog", canonical_key),
        ("pygog", legacy_key),
    ]


def test_delete_token_falls_back_to_legacy_raw_account_key(monkeypatch):
    account = " User@Example.COM "
    canonical_key = "token:default:user@example.com"
    legacy_key = f"token:default:{account}"
    delete_password = Mock(side_effect=[PasswordDeleteError("canonical key missing"), None])
    monkeypatch.setattr(keyring_module.keyring, "delete_password", delete_password)

    assert KeyringStorage("default").delete_token(account) is True
    assert [call.args for call in delete_password.call_args_list] == [
        ("pygog", canonical_key),
        ("pygog", legacy_key),
    ]


def test_service_account_private_material_is_stored_in_keyring(monkeypatch, tmp_path):
    config = Mock()
    config.get.return_value = []
    monkeypatch.setattr(keyring_module, "get_config", lambda: config)
    set_password = Mock()
    monkeypatch.setattr(keyring_module.keyring, "set_password", set_password)

    key_data = {
        "type": "service_account",
        "client_email": "robot@example.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\n",
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    ServiceAccountStorage().store_key("Robot@Example.COM", key_data)

    assert set_password.call_args.args[0] == "pygog"
    assert set_password.call_args.args[1] == "service-account:robot@example.com"
    assert "private_key" in json.loads(set_password.call_args.args[2])
    assert all("service_account:" not in str(call) for call in config.set.call_args_list)


def test_service_account_corrupt_data_is_typed(monkeypatch):
    config = Mock()
    config.get.return_value = ["robot@example.com"]
    monkeypatch.setattr(keyring_module, "get_config", lambda: config)
    monkeypatch.setattr(keyring_module.keyring, "get_password", Mock(return_value="not-json"))

    with pytest.raises(KeyringDataError, match="service account"):
        ServiceAccountStorage().get_key("robot@example.com")


def test_service_account_delete_removes_key_and_tracking_entry(monkeypatch):
    config = Mock()
    config.get.return_value = ["Robot@Example.COM", "other@example.com"]
    monkeypatch.setattr(keyring_module, "get_config", lambda: config)
    monkeypatch.setattr(keyring_module.keyring, "delete_password", Mock(return_value=None))

    storage = ServiceAccountStorage()
    assert storage.delete_key("robot@example.com") is True

    assert config.set.call_args.args == ("service_accounts", ["other@example.com"])


def test_service_account_backend_failure_is_typed(monkeypatch):
    config = Mock()
    config.get.return_value = []
    monkeypatch.setattr(keyring_module, "get_config", lambda: config)
    monkeypatch.setattr(
        keyring_module.keyring,
        "set_password",
        Mock(side_effect=KeyringError("backend unavailable")),
    )

    with pytest.raises(KeyringStorageError, match="backend unavailable"):
        ServiceAccountStorage().store_key(
            "robot@example.com",
            {
                "type": "service_account",
                "client_email": "robot@example.com",
                "private_key": "private",
                "token_uri": "https://oauth2.googleapis.com/token",
            },
        )


def test_insecure_keyring_backend_is_rejected():
    with pytest.raises(KeyringStorageError, match="Insecure"):
        configure_keyring_backend("file")


def test_auto_rejects_active_plaintext_keyring(monkeypatch):
    class PlaintextKeyring:
        pass

    monkeypatch.setattr(
        keyring_module.keyring, "get_keyring", Mock(return_value=PlaintextKeyring())
    )
    with pytest.raises(KeyringStorageError, match="insecure"):
        configure_keyring_backend("auto")


def test_auto_allows_unavailable_backend_for_compatibility(monkeypatch):
    class NoBackend:
        __module__ = "keyring.backends.fail"

    monkeypatch.setattr(keyring_module.keyring, "get_keyring", Mock(return_value=NoBackend()))
    configure_keyring_backend("auto")


def test_delete_token_requires_both_canonical_and_legacy_deletions(monkeypatch):
    account = " User@Example.COM "
    delete_password = Mock(side_effect=[None, None])
    monkeypatch.setattr(keyring_module.keyring, "delete_password", delete_password)
    monkeypatch.setattr(
        keyring_module.keyring,
        "get_password",
        Mock(side_effect=[None, json.dumps({"token": "still-present"})]),
    )

    assert KeyringStorage("default").delete_token(account) is False
    assert delete_password.call_count == 2


def test_add_account_does_not_mutate_config_value_before_set(monkeypatch):
    config = Mock()
    accounts = ["existing@example.com"]
    config.get.return_value = accounts
    config.set.side_effect = KeyringStorageError("config unavailable")
    monkeypatch.setattr(keyring_module, "get_config", lambda: config)

    with pytest.raises(KeyringStorageError):
        KeyringStorage().add_account_to_list("new@example.com")

    assert accounts == ["existing@example.com"]


def test_service_account_store_rolls_back_secret_when_index_update_fails(monkeypatch):
    config = Mock()
    config.get.return_value = []
    config.set.side_effect = KeyringStorageError("config unavailable")
    monkeypatch.setattr(keyring_module, "get_config", lambda: config)
    set_password = Mock()
    delete_password = Mock()
    monkeypatch.setattr(keyring_module.keyring, "set_password", set_password)
    monkeypatch.setattr(keyring_module.keyring, "delete_password", delete_password)
    key_data = {
        "type": "service_account",
        "client_email": "robot@example.com",
        "private_key": "private",
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    with pytest.raises(KeyringStorageError, match="config unavailable"):
        ServiceAccountStorage().store_key("robot@example.com", key_data)

    delete_password.assert_called_once_with("pygog", "service-account:robot@example.com")


def test_service_account_delete_restores_secret_when_index_update_fails(monkeypatch):
    config = Mock()
    config.get.return_value = ["robot@example.com"]
    config.set.side_effect = KeyringStorageError("config unavailable")
    monkeypatch.setattr(keyring_module, "get_config", lambda: config)
    value = json.dumps(
        {
            "type": "service_account",
            "client_email": "robot@example.com",
            "private_key": "private",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )
    monkeypatch.setattr(keyring_module.keyring, "get_password", Mock(return_value=value))
    monkeypatch.setattr(keyring_module.keyring, "delete_password", Mock(return_value=None))
    set_password = Mock()
    monkeypatch.setattr(keyring_module.keyring, "set_password", set_password)

    with pytest.raises(KeyringStorageError, match="config unavailable"):
        ServiceAccountStorage().delete_key("robot@example.com")

    set_password.assert_called_once_with("pygog", "service-account:robot@example.com", value)
