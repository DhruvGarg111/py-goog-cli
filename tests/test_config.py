import json
import os
from pathlib import PurePosixPath, PureWindowsPath
from unittest.mock import patch

import pytest

from pygog.config import (
    ENV_ACCOUNT,
    ENV_CLIENT,
    ENV_COLOR,
    ENV_JSON,
    ENV_KEYRING_BACKEND,
    ENV_KEYRING_PASSWORD,
    ENV_PLAIN,
    ENV_TIMEZONE,
    Config,
    ensure_config_dir,
    get_config,
    get_config_dir,
    get_config_path,
)
from pygog.errors import ConfigurationError


class BaseMockPath:
    def __init__(self, *args):
        self._path = str(self._pure_class(*args))

    def __truediv__(self, other):
        return self.__class__(self._pure_class(self._path) / other)

    def __str__(self):
        return self._path

    def __eq__(self, other):
        if isinstance(other, (PurePosixPath, PureWindowsPath)):
            return self._pure_class(self._path) == other
        return self._path == str(other)

    def exists(self):
        return False


class MockWindowsPath(BaseMockPath):
    _pure_class = PureWindowsPath

    @classmethod
    def home(cls):
        return cls("C:\\Users\\Test")


class MockPosixPath(BaseMockPath):
    _pure_class = PurePosixPath

    @classmethod
    def home(cls):
        return cls("/home/test")


class MockMacOSPath(MockPosixPath):
    @classmethod
    def home(cls):
        return cls("/Users/Test")

    def exists(self):
        return self._path == "/Library"


def test_get_config_dir_windows():
    with (
        patch("pygog.config.os.name", "nt"),
        patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}, clear=True),
        patch("pygog.config.Path", MockWindowsPath),
    ):
        assert get_config_dir() == PureWindowsPath("C:\\Users\\Test\\AppData\\Roaming\\pygog")


def test_get_config_dir_windows_no_appdata():
    with (
        patch("pygog.config.os.name", "nt"),
        patch.dict(os.environ, {}, clear=True),
        patch("pygog.config.Path", MockWindowsPath),
    ):
        assert get_config_dir() == PureWindowsPath("C:\\Users\\Test\\AppData\\Roaming\\pygog")


def test_get_config_dir_macos():
    with patch("pygog.config.os.name", "posix"), patch("pygog.config.Path", MockMacOSPath):
        assert get_config_dir() == PurePosixPath("/Users/Test/Library/Application Support/pygog")


def test_get_config_dir_linux_xdg():
    with (
        patch("pygog.config.os.name", "posix"),
        patch.dict(os.environ, {"XDG_CONFIG_HOME": "/home/test/.config"}, clear=True),
        patch("pygog.config.Path", MockPosixPath),
    ):
        with patch.object(MockPosixPath, "home", wraps=MockPosixPath.home) as mock_home:
            assert get_config_dir() == PurePosixPath("/home/test/.config/pygog")
            mock_home.assert_not_called()


def test_get_config_dir_linux_no_xdg():
    with (
        patch("pygog.config.os.name", "posix"),
        patch.dict(os.environ, {}, clear=True),
        patch("pygog.config.Path", MockPosixPath),
    ):
        assert get_config_dir() == PurePosixPath("/home/test/.config/pygog")


def test_get_config_dir_fallback():
    with patch("pygog.config.os.name", "unknown"), patch("pygog.config.Path", MockPosixPath):
        assert get_config_dir() == PurePosixPath("/home/test/.pygog")


@patch("pygog.config.get_config_dir")
def test_ensure_config_dir(mock_get_config_dir, tmp_path):
    mock_dir = tmp_path / "myconfig"
    mock_get_config_dir.return_value = mock_dir
    assert not mock_dir.exists()

    result = ensure_config_dir()

    assert result == mock_dir
    assert mock_dir.exists()
    assert mock_dir.is_dir()


@patch("pygog.config.get_config_dir")
def test_get_config_path(mock_get_config_dir):
    mock_get_config_dir.return_value = PurePosixPath("/mock/dir")
    assert get_config_path() == PurePosixPath("/mock/dir/config.json")


@pytest.fixture
def mock_config(tmp_path):
    config_file = tmp_path / "config.json"
    with patch("pygog.config.get_config_path", return_value=config_file):
        with patch("pygog.config.ensure_config_dir"):  # Prevent mkdir on mock path
            config = Config()
            yield config, config_file


def test_config_load_empty(mock_config):
    config, _ = mock_config
    config.load()
    assert config._data == {}
    assert config._loaded is True


def test_config_load_valid(mock_config):
    config, config_file = mock_config
    config_file.write_text('{"key": "value"}')
    config.load()
    assert config._data == {"key": "value"}


def test_config_load_invalid(mock_config):
    config, config_file = mock_config
    config_file.write_text("invalid json")
    with pytest.raises(ConfigurationError, match="config.json"):
        config.load()
    assert config._loaded is False
    assert config._data == {}


def test_config_load_malformed_json5_preserves_existing_file(mock_config):
    config, config_file = mock_config
    config_file.write_text('{"keep": "this",')

    with pytest.raises(ConfigurationError) as error:
        config.load()

    assert str(config_file) in str(error.value)
    assert config_file.read_text() == '{"keep": "this",'


def test_config_set_does_not_overwrite_malformed_file(mock_config):
    config, config_file = mock_config
    config_file.write_text("{broken")

    with pytest.raises(ConfigurationError):
        config.set("default_account", "user@example.com")

    assert config_file.read_text() == "{broken"


def test_config_stays_fail_closed_after_reload_becomes_malformed(mock_config):
    config, config_file = mock_config
    config_file.write_text('{"existing": "value"}')
    config.load()
    config_file.write_text("{broken")

    with pytest.raises(ConfigurationError):
        config.load()
    with pytest.raises(ConfigurationError):
        config.set("new_key", "new_value")

    assert config_file.read_text() == "{broken"


def test_config_set_rejects_service_account_secret_key(mock_config):
    config, _ = mock_config

    with pytest.raises(ConfigurationError, match="service account"):
        config.set("service_account:user@example.com", {"private_key": "secret"})


def test_config_set_rejects_service_account_container_key(mock_config):
    config, _ = mock_config

    with pytest.raises(ConfigurationError, match="service account"):
        config.set("service_account", {"private_key": "secret"})


def test_config_set_rejects_insecure_keyring_backend(mock_config):
    config, _ = mock_config

    with pytest.raises(ConfigurationError, match="insecure"):
        config.set("keyring_backend", "file")


def test_config_validates_known_mapping_types(mock_config):
    config, _ = mock_config

    with pytest.raises(ConfigurationError, match="account_aliases"):
        config.set("account_aliases", ["not", "a", "mapping"])


def test_config_save_is_atomic_and_restrictive(mock_config):
    config, config_file = mock_config
    config.set("default_account", "user@example.com")
    config_file.chmod(0o600)
    original = config_file.read_text()

    with patch("pygog.config.os.replace", side_effect=OSError("replace failed")):
        config._data["default_account"] = "new@example.com"
        with pytest.raises(ConfigurationError, match="replace failed"):
            config.save()

    assert config_file.read_text() == original
    if os.name != "nt":
        assert config_file.stat().st_mode & 0o777 == 0o600


def test_config_display_redacts_sensitive_keys_and_nested_values(mock_config):
    config, _ = mock_config
    config.set(
        "account_aliases",
        {"work": "user@example.com"},
    )
    config._data["oauth_client_secret"] = "super-secret"
    config._data["api_key"] = "api-secret"
    config._data["nested"] = {"refresh_token": "refresh-secret", "safe": "value"}

    displayed = config.get_all(redact=True)

    assert displayed["oauth_client_secret"] == "[REDACTED]"
    assert displayed["api_key"] == "[REDACTED]"
    assert displayed["nested"] == {"refresh_token": "[REDACTED]", "safe": "value"}
    assert config.get("oauth_client_secret") == "super-secret"
    assert config.get("oauth_client_secret", redact=True) == "[REDACTED]"


def test_config_loads_legacy_sensitive_values_for_redacted_display(mock_config):
    config, config_file = mock_config
    config_file.write_text(
        json.dumps({"api_key": "legacy-secret", "nested": {"password": "hidden"}})
    )

    config.load()

    assert config.get("api_key") == "legacy-secret"
    assert config.get_all(redact=True) == {
        "api_key": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
    }


def test_config_save(mock_config):
    config, config_file = mock_config
    config._data = {"key": "value"}
    config.save()
    assert config_file.exists()
    with open(config_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"key": "value"}


def test_config_get_set_unset(mock_config):
    config, _ = mock_config

    assert config.get("test_key") is None
    assert config.get("test_key", "default") == "default"

    config.set("test_key", "test_value")
    assert config.get("test_key") == "test_value"

    assert config.unset("test_key") is True
    assert config.get("test_key") is None
    assert config.unset("test_key") is False


def test_config_get_all_keys(mock_config):
    config, _ = mock_config
    config.set("key1", "val1")
    config.set("key2", "val2")

    assert config.get_all() == {"key1": "val1", "key2": "val2"}
    assert set(config.keys()) == {"key1", "key2"}


def test_config_properties(mock_config):
    config, _ = mock_config
    config.set("default_account", "test_acc")
    config.set("default_client", "test_cli")
    config.set("color", "never")
    config.set("default_timezone", "UTC")
    config.set("keyring_backend", "test_backend")

    with patch.dict(os.environ, {}, clear=True):
        assert config.account == "test_acc"
        assert config.client == "test_cli"
        assert config.json_output is False
        assert config.plain_output is False
        assert config.color_mode == "never"
        assert config.timezone == "UTC"
        assert config.keyring_backend == "test_backend"
        assert config.keyring_password is None


def test_config_properties_env_override(mock_config):
    config, _ = mock_config
    config.set("default_account", "test_acc")

    env_vars = {
        ENV_ACCOUNT: "env_acc",
        ENV_CLIENT: "env_cli",
        ENV_JSON: "true",
        ENV_PLAIN: "1",
        ENV_COLOR: "always",
        ENV_TIMEZONE: "PST",
        ENV_KEYRING_BACKEND: "env_backend",
        ENV_KEYRING_PASSWORD: "secret_password",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        assert config.account == "env_acc"
        assert config.client == "env_cli"
        assert config.json_output is True
        assert config.plain_output is True
        assert config.color_mode == "always"
        assert config.timezone == "PST"
        assert config.keyring_backend == "env_backend"
        assert config.keyring_password == "secret_password"


def test_config_resolve_account(mock_config):
    config, _ = mock_config
    config.set("default_account", "def_acc")
    config.set("account_aliases", {"work": "work@example.com"})

    with patch.dict(os.environ, {}, clear=True):
        assert config.resolve_account(None) == "def_acc"
        assert config.resolve_account("auto") == "def_acc"
        assert config.resolve_account("work") == "work@example.com"
        assert config.resolve_account("other") == "other"


@pytest.mark.parametrize("requested_account", [None, "auto"])
def test_config_resolve_account_applies_alias_to_default_account(mock_config, requested_account):
    config, _ = mock_config
    config.set("default_account", "work")
    config.set("account_aliases", {"work": "work@example.com"})

    with patch.dict(os.environ, {}, clear=True):
        assert config.resolve_account(requested_account) == "work@example.com"


@pytest.mark.parametrize("requested_account", [None, "auto"])
def test_config_resolve_account_applies_alias_to_environment_account(
    mock_config, requested_account
):
    config, _ = mock_config
    config.set("account_aliases", {"personal": "personal@example.net"})

    with patch.dict(os.environ, {ENV_ACCOUNT: "personal"}, clear=True):
        assert config.resolve_account(requested_account) == "personal@example.net"


def test_config_get_client_for_account_casefolds_domain(mock_config):
    config, _ = mock_config
    config.set("client_domains", {"example.com": "domain_cli"})

    assert config.get_client_for_account("user@EXAMPLE.COM") == "domain_cli"


def test_config_get_returns_defensive_mutable_copy(mock_config):
    config, _ = mock_config
    config.set("account_aliases", {"work": "user@example.com"})
    aliases = config.get("account_aliases")
    aliases["stolen"] = "attacker@example.com"
    assert config.get("account_aliases") == {"work": "user@example.com"}


def test_config_get_client_for_account(mock_config):
    config, _ = mock_config
    config.set("default_client", "def_cli")
    config.set("account_clients", {"test@test.com": "test_cli"})
    config.set("client_domains", {"work.com": "work_cli"})

    with patch.dict(os.environ, {}, clear=True):
        assert config.get_client_for_account("test@test.com") == "test_cli"
        assert config.get_client_for_account("user@work.com") == "work_cli"
        assert config.get_client_for_account("other@example.com") == "def_cli"


def test_get_config_singleton():
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2


def test_config_path_property(mock_config):
    config, config_file = mock_config
    assert config.path == config_file
