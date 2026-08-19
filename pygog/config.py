"""Secure configuration management for pygog."""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import json5

from pygog.errors import ConfigurationError

CONFIG_FILE = "config.json"

ENV_ACCOUNT = "GOG_ACCOUNT"
ENV_CLIENT = "GOG_CLIENT"
ENV_JSON = "GOG_JSON"
ENV_PLAIN = "GOG_PLAIN"
ENV_COLOR = "GOG_COLOR"
ENV_TIMEZONE = "GOG_TIMEZONE"
ENV_KEYRING_BACKEND = "GOG_KEYRING_BACKEND"
ENV_KEYRING_PASSWORD = "GOG_KEYRING_PASSWORD"
ENV_ENABLE_COMMANDS = "GOG_ENABLE_COMMANDS"

REDACTED = "[REDACTED]"
_SERVICE_ACCOUNT_PREFIX = "service_account:"
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
    "password",
    "credential",
    "secret",
    "token",
)
_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


class ConfigError(ConfigurationError):
    """Backward-compatible name for invalid or unsafe configuration."""


def _error(message: str, path: Path | None = None) -> ConfigurationError:
    """Build a configuration error that always identifies its file when known."""
    if path is not None:
        message = f"{message} (configuration file: {path})"
        return ConfigError(message, details={"path": str(path)})
    return ConfigError(message)


def _is_sensitive_key(key: str) -> bool:
    """Return whether a key is likely to contain secret material."""
    lowered = key.casefold()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS) or lowered.endswith(":private")


def _redact(value: Any, *, sensitive: bool = False) -> Any:
    """Return a display-safe copy of a configuration value."""
    if sensitive:
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(key): _redact(item, sensitive=_is_sensitive_key(str(key)))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _validate_string_mapping(key: str, value: Any) -> None:
    if not isinstance(value, Mapping) or any(
        not isinstance(item_key, str) or not isinstance(item_value, str)
        for item_key, item_value in value.items()
    ):
        raise ValueError(f"{key} must be a mapping of strings to strings")


def _validate_value(key: str, value: Any, *, reject_sensitive: bool = True) -> None:
    """Validate a key/value pair before it can reach the config file."""
    if not isinstance(key, str) or not key:
        raise ValueError("configuration keys must be non-empty safe identifiers")
    lowered = key.casefold()
    if lowered == "service_account" or lowered.startswith(_SERVICE_ACCOUNT_PREFIX):
        raise ValueError(
            "service account private material must be stored in the OS keyring, "
            "not in configuration"
        )
    if not _KEY_RE.fullmatch(key):
        raise ValueError("configuration keys must be non-empty safe identifiers")
    if reject_sensitive and _is_sensitive_key(key):
        raise ValueError(f"configuration key '{key}' is reserved for secret storage")

    if key in {"default_account", "default_client", "default_timezone", "keyring_backend"}:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        if key == "keyring_backend" and value.strip().casefold() in {
            "file",
            "plaintext",
            "null",
        }:
            raise ValueError("insecure keyring backends are not supported")
    elif key == "color":
        if value not in {"auto", "always", "never"}:
            raise ValueError("color must be one of: auto, always, never")
    elif key in {"account_aliases", "account_clients", "client_domains"}:
        _validate_string_mapping(key, value)
    elif key == "service_accounts":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("service_accounts must be a list of strings")
    elif key.startswith("accounts:"):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{key} must be a list of strings")
    elif key == "enable_commands":
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("enable_commands must be a list of strings")

    # Validate unknown values for JSON safety as well.  This prevents a failed
    # serialization after the in-memory state has already been changed.
    json.dumps(value, allow_nan=False)


def _validate_document(
    data: Any,
    path: Path | None = None,
    *,
    reject_sensitive: bool = False,
) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        raise _error("configuration must contain a top-level object", path)
    validated: dict[str, Any] = {}
    for key, value in data.items():
        try:
            _validate_value(key, value, reject_sensitive=reject_sensitive)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise _error(str(exc), path) from exc
        validated[key] = value
    return validated


def get_config_dir() -> Path:
    """Get OS-appropriate config directory."""
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "pygog"
        return Path.home() / "AppData" / "Roaming" / "pygog"

    if os.name == "posix":
        if Path("/Library").exists():  # macOS
            return Path.home() / "Library" / "Application Support" / "pygog"

        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "pygog"
        return Path.home() / ".config" / "pygog"

    return Path.home() / ".pygog"


def _restrictive_mode(path: Path, mode: int = 0o600) -> None:
    """Apply a private mode where the platform exposes POSIX permissions."""
    try:
        os.chmod(path, mode)
    except (AttributeError, NotImplementedError, OSError):
        # Windows ACLs are managed by the OS; chmod is not a reliable ACL API.
        pass


def ensure_config_dir() -> Path:
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    _restrictive_mode(config_dir, 0o700)
    return config_dir


def get_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync after an atomic replacement."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(str(path), flags)
    except (AttributeError, OSError):
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write_json(path: Path, data: Mapping[str, Any], *, mode: int = 0o600) -> None:
    """Write JSON through a same-directory, flushed, atomically replaced file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(data, temporary, indent=2, ensure_ascii=False, allow_nan=False)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        _restrictive_mode(temporary_path, mode)
        os.replace(temporary_path, path)
        temporary_path = None
        _restrictive_mode(path, mode)
        _fsync_directory(path.parent)
    except (OSError, TypeError, ValueError, OverflowError, RecursionError) as exc:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass
        raise _error(f"unable to atomically write configuration: {exc}", path) from exc


class Config:
    def __init__(self):
        self._data: dict[str, Any] = {}
        self._loaded = False
        self._path = get_config_path()

    def load(self) -> None:
        if not self._path.exists():
            self._data = {}
            self._loaded = True
            return

        try:
            with open(self._path, encoding="utf-8") as file:
                parsed = json5.load(file)
            validated = _validate_document(parsed, self._path)
        except ConfigurationError:
            self._loaded = False
            raise
        except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
            # Keep the previously parsed data as a recovery aid, but mark the
            # object unloaded so a later set() must fail closed instead of
            # overwriting the only recovery copy.
            self._loaded = False
            raise _error(f"unable to parse configuration: {exc}", self._path) from exc

        self._data = validated
        self._loaded = True

    def save(self) -> None:
        # A caller may prepare _data directly before the first save (the
        # historical API allowed this), but an existing file must be loaded
        # first so a malformed file can never be replaced accidentally.
        if not self._loaded:
            if self._path.exists():
                self.load()
            else:
                self._loaded = True
        try:
            validated = _validate_document(self._data, self._path)
        except ConfigurationError:
            raise
        atomic_write_json(self._path, validated)
        self._data = validated

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def get(self, key: str, default: Any = None, *, redact: bool = False) -> Any:
        self._ensure_loaded()
        value = self._data.get(key, default)
        if redact:
            return _redact(value, sensitive=_is_sensitive_key(key))
        return copy.deepcopy(value)

    def set(self, key: str, value: Any) -> None:
        self._ensure_loaded()
        try:
            _validate_value(key, value)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise _error(str(exc), self._path) from exc
        previous = copy.deepcopy(self._data)
        self._data[key] = value
        try:
            self.save()
        except Exception:
            self._data = previous
            raise

    def unset(self, key: str) -> bool:
        self._ensure_loaded()
        if key not in self._data:
            return False
        previous = copy.deepcopy(self._data)
        del self._data[key]
        try:
            self.save()
        except Exception:
            self._data = previous
            raise
        return True

    def get_all(self, *, redact: bool = False) -> dict[str, Any]:
        self._ensure_loaded()
        if redact:
            return cast(dict[str, Any], _redact(self._data))
        return copy.deepcopy(self._data)

    def get_safe_all(self) -> dict[str, Any]:
        """Return configuration suitable for display or logs."""
        return self.get_all(redact=True)

    def keys(self) -> list[str]:
        self._ensure_loaded()
        return list(self._data.keys())

    @property
    def path(self) -> Path:
        return cast(Path, self._path)

    @property
    def account(self) -> str | None:
        return os.environ.get(ENV_ACCOUNT) or self.get("default_account")

    @property
    def client(self) -> str:
        return cast(str, os.environ.get(ENV_CLIENT) or self.get("default_client", "default"))

    @property
    def json_output(self) -> bool:
        return os.environ.get(ENV_JSON, "").lower() in ("1", "true", "yes")

    @property
    def plain_output(self) -> bool:
        return os.environ.get(ENV_PLAIN, "").lower() in ("1", "true", "yes")

    @property
    def color_mode(self) -> str:
        return cast(str, os.environ.get(ENV_COLOR) or self.get("color", "auto"))

    @property
    def timezone(self) -> str | None:
        return os.environ.get(ENV_TIMEZONE) or self.get("default_timezone")

    @property
    def keyring_backend(self) -> str:
        # The keyring module applies this setting when a storage object is
        # constructed; this property remains for compatibility with scripts.
        return cast(str, os.environ.get(ENV_KEYRING_BACKEND) or self.get("keyring_backend", "auto"))

    @property
    def keyring_password(self) -> str | None:
        return os.environ.get(ENV_KEYRING_PASSWORD)

    @property
    def account_aliases(self) -> dict[str, str]:
        return cast(dict[str, str], self.get("account_aliases", {}))

    @property
    def account_clients(self) -> dict[str, str]:
        return cast(dict[str, str], self.get("account_clients", {}))

    @property
    def client_domains(self) -> dict[str, str]:
        return cast(dict[str, str], self.get("client_domains", {}))

    def resolve_account(self, account: str | None) -> str | None:
        selected_account = self.account if account in (None, "auto") else account
        if selected_account is None:
            return None
        return self.account_aliases.get(selected_account, selected_account)

    def get_client_for_account(self, account: str) -> str:
        explicit_client = os.environ.get(ENV_CLIENT)
        if explicit_client:
            return explicit_client

        if account in self.account_clients:
            return self.account_clients[account]

        if "@" in account:
            domain = account.split("@", 1)[1].casefold()
            for configured_domain, client in self.client_domains.items():
                if configured_domain.casefold() == domain:
                    return client

        return cast(str, self.get("default_client", "default"))


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


__all__ = [
    "CONFIG_FILE",
    "Config",
    "ConfigError",
    "ConfigurationError",
    "REDACTED",
    "atomic_write_json",
    "ensure_config_dir",
    "get_config",
    "get_config_dir",
    "get_config_path",
]
