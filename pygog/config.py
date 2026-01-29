"""Configuration management for pygog."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import json5

# Default config file name
CONFIG_FILE = "config.json"

# Environment variable names
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
    """Get the configuration directory path.
    
    Returns OS-appropriate config directory:
    - Windows: %APPDATA%/pygog
    - macOS: ~/Library/Application Support/pygog
    - Linux: ~/.config/pygog or $XDG_CONFIG_HOME/pygog
    """
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / "pygog"
    elif os.name == "posix":
        # macOS
        if Path("/Library").exists():
            return Path.home() / "Library" / "Application Support" / "pygog"
        # Linux
        xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(xdg_config) / "pygog"
    else:
        return Path.home() / ".pygog"


def ensure_config_dir() -> Path:
    """Ensure config directory exists and return its path."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_config_dir() / CONFIG_FILE


class Config:
    """Configuration manager for pygog."""

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._loaded = False
        self._path = get_config_path()

    def load(self) -> None:
        """Load configuration from file."""
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._data = json5.load(f)
            except (json.JSONDecodeError, ValueError):
                self._data = {}
        self._loaded = True

    def save(self) -> None:
        """Save configuration to file."""
        ensure_config_dir()
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def _ensure_loaded(self) -> None:
        """Ensure config is loaded."""
        if not self._loaded:
            self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        self._ensure_loaded()
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._ensure_loaded()
        self._data[key] = value
        self.save()

    def unset(self, key: str) -> bool:
        """Remove a configuration value. Returns True if key existed."""
        self._ensure_loaded()
        if key in self._data:
            del self._data[key]
            self.save()
            return True
        return False

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values."""
        self._ensure_loaded()
        return dict(self._data)

    def keys(self) -> list[str]:
        """Get all configuration keys."""
        self._ensure_loaded()
        return list(self._data.keys())

    @property
    def path(self) -> Path:
        """Get the config file path."""
        return self._path

    # Convenience properties with env override
    @property
    def account(self) -> str | None:
        """Get the default account (from env or config)."""
        return os.environ.get(ENV_ACCOUNT) or self.get("default_account")

    @property
    def client(self) -> str:
        """Get the OAuth client name (from env or config)."""
        return os.environ.get(ENV_CLIENT) or self.get("default_client", "default")

    @property
    def json_output(self) -> bool:
        """Check if JSON output is enabled."""
        return os.environ.get(ENV_JSON, "").lower() in ("1", "true", "yes")

    @property
    def plain_output(self) -> bool:
        """Check if plain output is enabled."""
        return os.environ.get(ENV_PLAIN, "").lower() in ("1", "true", "yes")

    @property
    def color_mode(self) -> str:
        """Get color mode (auto, always, never)."""
        return os.environ.get(ENV_COLOR) or self.get("color", "auto")

    @property
    def timezone(self) -> str | None:
        """Get default timezone."""
        return os.environ.get(ENV_TIMEZONE) or self.get("default_timezone")

    @property
    def keyring_backend(self) -> str:
        """Get keyring backend (auto, keychain, file)."""
        return os.environ.get(ENV_KEYRING_BACKEND) or self.get("keyring_backend", "auto")

    @property
    def keyring_password(self) -> str | None:
        """Get keyring password for file backend."""
        return os.environ.get(ENV_KEYRING_PASSWORD)

    @property
    def account_aliases(self) -> dict[str, str]:
        """Get account aliases mapping."""
        return self.get("account_aliases", {})

    @property
    def account_clients(self) -> dict[str, str]:
        """Get account to client mapping."""
        return self.get("account_clients", {})

    @property
    def client_domains(self) -> dict[str, str]:
        """Get domain to client mapping."""
        return self.get("client_domains", {})

    def resolve_account(self, account: str | None) -> str | None:
        """Resolve account alias to email."""
        if account is None:
            return self.account
        if account == "auto":
            return self.account
        # Check if it's an alias
        aliases = self.account_aliases
        return aliases.get(account, account)

    def get_client_for_account(self, account: str) -> str:
        """Get the OAuth client for a specific account."""
        # Check explicit account mapping
        if account in self.account_clients:
            return self.account_clients[account]
        # Check domain mapping
        if "@" in account:
            domain = account.split("@")[1]
            if domain in self.client_domains:
                return self.client_domains[domain]
        # Use default client
        return self.client


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
