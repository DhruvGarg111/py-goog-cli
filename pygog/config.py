"""Configuration management for pygog."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import json5

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


def get_config_dir() -> Path:
    """Get OS-appropriate config directory."""
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / "pygog"
    
    if os.name == "posix":
        if Path("/Library").exists(): # macOS
            return Path.home() / "Library" / "Application Support" / "pygog"
        
        # Linux
        xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(xdg_config) / "pygog"
    
    return Path.home() / ".pygog"


def ensure_config_dir() -> Path:
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE


class Config:
    def __init__(self):
        self._data: dict[str, Any] = {}
        self._loaded = False
        self._path = get_config_path()

    def load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._data = json5.load(f)
            except (json.JSONDecodeError, ValueError):
                self._data = {}
        self._loaded = True

    def save(self) -> None:
        ensure_config_dir()
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._ensure_loaded()
        self._data[key] = value
        self.save()

    def unset(self, key: str) -> bool:
        self._ensure_loaded()
        if key in self._data:
            del self._data[key]
            self.save()
            return True
        return False

    def get_all(self) -> dict[str, Any]:
        self._ensure_loaded()
        return dict(self._data)

    def keys(self) -> list[str]:
        self._ensure_loaded()
        return list(self._data.keys())

    @property
    def path(self) -> Path:
        return self._path

    @property
    def account(self) -> str | None:
        return os.environ.get(ENV_ACCOUNT) or self.get("default_account")

    @property
    def client(self) -> str:
        return os.environ.get(ENV_CLIENT) or self.get("default_client", "default")

    @property
    def json_output(self) -> bool:
        return os.environ.get(ENV_JSON, "").lower() in ("1", "true", "yes")

    @property
    def plain_output(self) -> bool:
        return os.environ.get(ENV_PLAIN, "").lower() in ("1", "true", "yes")

    @property
    def color_mode(self) -> str:
        return os.environ.get(ENV_COLOR) or self.get("color", "auto")

    @property
    def timezone(self) -> str | None:
        return os.environ.get(ENV_TIMEZONE) or self.get("default_timezone")

    @property
    def keyring_backend(self) -> str:
        return os.environ.get(ENV_KEYRING_BACKEND) or self.get("keyring_backend", "auto")

    @property
    def keyring_password(self) -> str | None:
        return os.environ.get(ENV_KEYRING_PASSWORD)

    @property
    def account_aliases(self) -> dict[str, str]:
        return self.get("account_aliases", {})

    @property
    def account_clients(self) -> dict[str, str]:
        return self.get("account_clients", {})

    @property
    def client_domains(self) -> dict[str, str]:
        return self.get("client_domains", {})

    def resolve_account(self, account: str | None) -> str | None:
        if account is None:
            return self.account
        if account == "auto":
            return self.account
            
        return self.account_aliases.get(account, account)

    def get_client_for_account(self, account: str) -> str:
        if account in self.account_clients:
            return self.account_clients[account]
            
        if "@" in account:
            domain = account.split("@")[1]
            if domain in self.client_domains:
                return self.client_domains[domain]
                
        return self.client


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
