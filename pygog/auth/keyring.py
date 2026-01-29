"""Keyring storage for OAuth tokens."""

from __future__ import annotations

import json
from typing import Any

import keyring
from keyring.errors import KeyringError

from pygog.config import get_config, ensure_config_dir

# Service name for keyring
KEYRING_SERVICE = "pygog"


class KeyringStorage:
    """Secure storage for OAuth tokens using system keyring."""

    def __init__(self, client: str = "default"):
        """Initialize keyring storage.
        
        Args:
            client: OAuth client name for namespace isolation
        """
        self.client = client
        self._config = get_config()

    def _make_key(self, account: str) -> str:
        """Create a keyring key for an account."""
        return f"token:{self.client}:{account}"

    def store_token(self, account: str, token_data: dict[str, Any]) -> None:
        """Store a token for an account.
        
        Args:
            account: Account email
            token_data: Token data including refresh_token, etc.
        """
        key = self._make_key(account)
        value = json.dumps(token_data)
        try:
            keyring.set_password(KEYRING_SERVICE, key, value)
        except KeyringError as e:
            raise RuntimeError(f"Failed to store token in keyring: {e}") from e

    def get_token(self, account: str) -> dict[str, Any] | None:
        """Retrieve a token for an account.
        
        Args:
            account: Account email
            
        Returns:
            Token data or None if not found
        """
        key = self._make_key(account)
        try:
            value = keyring.get_password(KEYRING_SERVICE, key)
            if value:
                return json.loads(value)
            return None
        except KeyringError:
            return None
        except json.JSONDecodeError:
            return None

    def delete_token(self, account: str) -> bool:
        """Delete a token for an account.
        
        Args:
            account: Account email
            
        Returns:
            True if token was deleted
        """
        key = self._make_key(account)
        try:
            keyring.delete_password(KEYRING_SERVICE, key)
            return True
        except KeyringError:
            return False

    def list_accounts(self) -> list[str]:
        """List all stored accounts for this client.
        
        Note: This is a best-effort implementation. Some keyring backends
        don't support listing, so we also track accounts in config.
        
        Returns:
            List of account emails
        """
        config = self._config
        stored_accounts = config.get(f"accounts:{self.client}", [])
        return stored_accounts

    def add_account_to_list(self, account: str) -> None:
        """Add account to the tracked list."""
        config = self._config
        key = f"accounts:{self.client}"
        accounts = config.get(key, [])
        if account not in accounts:
            accounts.append(account)
            config.set(key, accounts)

    def remove_account_from_list(self, account: str) -> None:
        """Remove account from the tracked list."""
        config = self._config
        key = f"accounts:{self.client}"
        accounts = config.get(key, [])
        if account in accounts:
            accounts.remove(account)
            config.set(key, accounts)


class ServiceAccountStorage:
    """Storage for service account keys."""

    def __init__(self):
        self._config = get_config()

    def _make_key(self, account: str) -> str:
        """Create a config key for service account."""
        return f"service_account:{account}"

    def store_key(self, account: str, key_data: dict[str, Any]) -> None:
        """Store service account key for an account."""
        config_key = self._make_key(account)
        # Store in config (could also use keyring for more security)
        self._config.set(config_key, key_data)

    def get_key(self, account: str) -> dict[str, Any] | None:
        """Get service account key for an account."""
        config_key = self._make_key(account)
        return self._config.get(config_key)

    def delete_key(self, account: str) -> bool:
        """Delete service account key for an account."""
        config_key = self._make_key(account)
        return self._config.unset(config_key)

    def has_key(self, account: str) -> bool:
        """Check if account has a service account key."""
        return self.get_key(account) is not None
