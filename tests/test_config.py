import json
import os
import sys
from pathlib import Path, PureWindowsPath
from unittest.mock import patch, MagicMock

import pytest
import json5

from pygog.config import (
    get_config_dir,
    ensure_config_dir,
    get_config_path,
    Config,
    get_config,
    ENV_ACCOUNT,
    ENV_CLIENT,
    ENV_JSON,
    ENV_PLAIN,
    ENV_COLOR,
    ENV_TIMEZONE,
    ENV_KEYRING_BACKEND,
    ENV_KEYRING_PASSWORD,
)


def test_get_config_dir_windows():
    # Since we can't instantiate WindowsPath on non-Windows systems easily without triggering NotImplementedError
    # when path is constructed, we'll patch the path construction if possible or mock the whole logic.
    with patch("os.name", "nt"), \
         patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}, clear=True):

        # When APPDATA is set, Path.home() isn't called, base becomes just the string.
        # But Path(base) will try to instantiate WindowsPath if os.name is 'nt' on some python versions
        # wait, os.name='nt' might cause Path(base) to become WindowsPath and fail.
        # We can mock Path inside config module.
        with patch("pygog.config.Path") as mock_path:
            mock_path.return_value = MagicMock()
            mock_path.return_value.__truediv__.return_value = "mocked_path"

            assert get_config_dir() == "mocked_path"
            mock_path.assert_called_once_with("C:\\Users\\Test\\AppData\\Roaming")
            mock_path.return_value.__truediv__.assert_called_once_with("pygog")


def test_get_config_dir_windows_no_appdata():
    with patch("os.name", "nt"), \
         patch.dict(os.environ, {}, clear=True):

        with patch("pygog.config.Path") as mock_path:
            mock_path.home.return_value = MagicMock()
            mock_path.home.return_value.__truediv__.return_value.__truediv__.return_value = "mock_home_appdata"

            mock_path.return_value = MagicMock()
            mock_path.return_value.__truediv__.return_value = "mock_final_path"

            assert get_config_dir() == "mock_final_path"
            mock_path.assert_called_once_with("mock_home_appdata")

def test_get_config_dir_macos():
    with patch("os.name", "posix"), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.home", return_value=Path("/Users/Test")):
        assert get_config_dir() == Path("/Users/Test/Library/Application Support/pygog")

def test_get_config_dir_linux_xdg():
    with patch("os.name", "posix"), \
         patch("pathlib.Path.exists", return_value=False), \
         patch.dict(os.environ, {"XDG_CONFIG_HOME": "/home/test/.config"}, clear=True):
        assert get_config_dir() == Path("/home/test/.config/pygog")

def test_get_config_dir_linux_no_xdg():
    with patch("os.name", "posix"), \
         patch("pathlib.Path.exists", return_value=False), \
         patch.dict(os.environ, {}, clear=True), \
         patch("pathlib.Path.home", return_value=Path("/home/test")):
        assert get_config_dir() == Path("/home/test/.config/pygog")

def test_get_config_dir_fallback():
    with patch("os.name", "unknown"), \
         patch("pathlib.Path.home", return_value=Path("/home/test")):
        assert get_config_dir() == Path("/home/test/.pygog")

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
    mock_get_config_dir.return_value = Path("/mock/dir")
    assert get_config_path() == Path("/mock/dir/config.json")


@pytest.fixture
def mock_config(tmp_path):
    config_file = tmp_path / "config.json"
    with patch("pygog.config.get_config_path", return_value=config_file):
        with patch("pygog.config.ensure_config_dir"): # Prevent mkdir on mock path
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
    config_file.write_text('invalid json')
    config.load()
    assert config._data == {}

def test_config_save(mock_config):
    config, config_file = mock_config
    config._data = {"key": "value"}
    config.save()
    assert config_file.exists()
    with open(config_file, "r") as f:
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
        ENV_KEYRING_PASSWORD: "secret_password"
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
    # Test that get_config returns a singleton instance
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2


def test_config_path_property(mock_config):
    config, config_file = mock_config
    assert config.path == config_file
