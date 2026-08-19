"""Offline tests for secure OAuth client credential storage."""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

import pytest

import pygog.auth.credentials as credentials_module
from pygog.auth.credentials import CredentialsError, CredentialsManager


def _manager(tmp_path, monkeypatch, client="default"):
    config_dir = tmp_path / "pygog"
    monkeypatch.setattr(credentials_module, "ensure_config_dir", lambda: config_dir)
    return CredentialsManager(client), config_dir


def _valid_credentials():
    return {
        "installed": {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def test_store_validates_nested_oauth_credentials_and_uses_private_permissions(
    tmp_path, monkeypatch
):
    manager, config_dir = _manager(tmp_path, monkeypatch)
    source = tmp_path / "downloaded.json"
    source.write_text(json.dumps(_valid_credentials()))

    manager.store(source)

    assert manager.load() == _valid_credentials()
    assert manager._path.parent == config_dir
    if os.name != "nt":
        assert manager._path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        {},
        {"installed": []},
        {"installed": {"client_id": "only"}},
        {"installed": {"client_id": "id", "client_secret": 42}},
    ],
)
def test_store_rejects_malformed_or_incomplete_credentials(tmp_path, monkeypatch, payload):
    manager, _ = _manager(tmp_path, monkeypatch)
    source = tmp_path / "downloaded.json"
    source.write_text(payload if isinstance(payload, str) else json.dumps(payload))

    with pytest.raises(CredentialsError):
        manager.store(source)

    assert not manager.exists()


def test_malformed_stored_credentials_raise_typed_error(tmp_path, monkeypatch):
    manager, _ = _manager(tmp_path, monkeypatch)
    manager._path.parent.mkdir(parents=True)
    manager._path.write_text("{broken")

    with pytest.raises(CredentialsError, match="stored"):
        manager.load()


def test_store_failure_preserves_previous_credentials(tmp_path, monkeypatch):
    manager, _ = _manager(tmp_path, monkeypatch)
    source = tmp_path / "downloaded.json"
    source.write_text(json.dumps(_valid_credentials()))
    manager.store(source)
    original = manager._path.read_text()

    replacement = _valid_credentials()
    replacement["installed"]["client_id"] = "new-client"
    source.write_text(json.dumps(replacement))
    with patch("pygog.config.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(CredentialsError, match="replace failed"):
            manager.store(source)

    assert manager._path.read_text() == original


def test_invalid_domain_is_rejected_before_credentials_are_written(tmp_path, monkeypatch):
    manager, _ = _manager(tmp_path, monkeypatch)
    config = Mock()
    config.get.return_value = {}
    monkeypatch.setattr(credentials_module, "get_config", lambda: config)
    source = tmp_path / "downloaded.json"
    source.write_text(json.dumps(_valid_credentials()))

    with pytest.raises(CredentialsError, match="domain"):
        manager.store(source, domain="not a domain")

    assert not manager.exists()
