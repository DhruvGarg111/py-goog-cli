"""Keyring storage for OAuth tokens."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, cast

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from pygog.config import get_config

KEYRING_SERVICE = "pygog"
SERVICE_ACCOUNT_KEY_PREFIX = "service-account:"


class KeyringStorageError(RuntimeError):
    """Raised when the configured keyring backend cannot be used."""


class KeyringDataError(KeyringStorageError):
    """Raised when a stored keyring value is not valid token JSON."""


def configure_keyring_backend(backend_name: str = "auto") -> None:
    """Select a real OS keyring backend, refusing insecure file backends."""
    if not isinstance(backend_name, str) or not backend_name.strip():
        raise KeyringStorageError("Keyring backend must be a non-empty string")

    name = backend_name.strip().casefold()
    if name == "auto":
        backend = keyring.get_keyring()
        backend_type = type(backend)
        backend_label = f"{backend_type.__module__}.{backend_type.__name__}".casefold()
        if any(marker in backend_label for marker in ("plaintext", "filekeyring", ".null")):
            raise KeyringStorageError("insecure plaintext/file/null keyring backend is active")
        return
    if name in {"file", "plaintext", "null"}:
        raise KeyringStorageError("Insecure file/plaintext keyring backends are not supported")
    if name not in {"keychain", "native"}:
        raise KeyringStorageError(
            f"Unknown keyring backend '{backend_name}'. Use 'auto' or 'keychain'."
        )

    try:
        configured_backend: Any
        if os.name == "nt":
            from keyring.backends.Windows import WinVaultKeyring

            configured_backend = WinVaultKeyring()
        elif sys.platform == "darwin":
            from keyring.backends.macOS import Keyring

            configured_backend = Keyring()
        else:
            from keyring.backends.SecretService import Keyring

            configured_backend = Keyring()
        keyring.set_keyring(configured_backend)
    except Exception as exc:
        raise KeyringStorageError(
            f"Unable to initialize keyring backend '{backend_name}': {exc}"
        ) from exc


def _normalise_account(account: str) -> str:
    """Return the canonical key form used for Google account identifiers."""
    if not isinstance(account, str) or not account.strip():
        raise ValueError("Account identifier must be a non-empty string")
    return account.strip().casefold()


def _validate_token_data(token_data: Any) -> dict[str, Any]:
    """Validate the minimum authorized-user token JSON contract."""
    if not isinstance(token_data, dict) or not token_data:
        raise KeyringDataError("Stored keyring value is not token data")

    token = token_data.get("token")
    refresh_token = token_data.get("refresh_token")
    if token is not None and not isinstance(token, str):
        raise KeyringDataError("Stored keyring token field must be a string or null")
    if refresh_token is not None and not isinstance(refresh_token, str):
        raise KeyringDataError("Stored keyring refresh_token field must be a string or null")
    if not (token and token.strip()) and not (refresh_token and refresh_token.strip()):
        raise KeyringDataError("Stored keyring value is not token data")

    string_fields = (
        "token_uri",
        "client_id",
        "client_secret",
        "account",
        "verified_account",
        "expiry",
    )
    for field in string_fields:
        value = token_data.get(field)
        if value is not None and not isinstance(value, str):
            raise KeyringDataError(f"Stored keyring {field} field must be a string or null")

    scopes = token_data.get("scopes")
    if scopes is not None and (
        not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes)
    ):
        raise KeyringDataError("Stored keyring scopes field must be a list of strings")

    return token_data


class KeyringStorage:
    """Secure storage for OAuth tokens using system keyring."""

    def __init__(self, client: str = "default"):
        """Initialize keyring storage.

        Args:
            client: OAuth client name for namespace isolation
        """
        self.client = client
        self._config = get_config()
        backend = self._config.keyring_backend
        if isinstance(backend, str):
            configure_keyring_backend(backend)

    def _make_key(self, account: str) -> str:
        """Create a keyring key for an account."""
        return f"token:{self.client}:{_normalise_account(account)}"

    def _make_legacy_key(self, account: str) -> str:
        """Create the pre-normalization key for backward-compatible reads."""
        _normalise_account(account)
        return f"token:{self.client}:{account}"

    def store_token(self, account: str, token_data: dict[str, Any]) -> None:
        """Store a token for an account.

        Args:
            account: Account email
            token_data: Token data including refresh_token, etc.
        """
        key = self._make_key(account)
        try:
            value = json.dumps(token_data)
        except (TypeError, ValueError, OverflowError, RecursionError) as e:
            raise KeyringStorageError(f"Failed to serialize token for keyring: {e}") from e
        _validate_token_data(token_data)
        try:
            keyring.set_password(KEYRING_SERVICE, key, value)
        except KeyringError as e:
            raise KeyringStorageError(f"Failed to store token in keyring: {e}") from e
        except Exception as e:
            raise KeyringStorageError(f"Failed to store token in keyring: {e}") from e

    def get_token(self, account: str) -> dict[str, Any] | None:
        """Retrieve a token for an account.

        Args:
            account: Account email

        Returns:
            Token data or None if not found
        """
        key = self._make_key(account)
        legacy_key = self._make_legacy_key(account)
        try:
            value = keyring.get_password(KEYRING_SERVICE, key)
            if not value and legacy_key != key:
                value = keyring.get_password(KEYRING_SERVICE, legacy_key)
        except KeyringError as e:
            raise KeyringStorageError(f"Failed to read token from keyring: {e}") from e
        except Exception as e:
            raise KeyringStorageError(f"Failed to read token from keyring: {e}") from e

        if not value:
            return None
        try:
            return _validate_token_data(json.loads(value))
        except (json.JSONDecodeError, TypeError) as e:
            raise KeyringDataError(f"Stored token for account '{account}' is corrupt JSON") from e

    def delete_token(self, account: str) -> bool:
        """Delete a token for an account.

        Args:
            account: Account email

        Returns:
            True if token was deleted
        """
        key = self._make_key(account)
        legacy_key = self._make_legacy_key(account)
        deleted = []
        for candidate in dict.fromkeys((key, legacy_key)):
            try:
                keyring.delete_password(KEYRING_SERVICE, candidate)
            except PasswordDeleteError:
                deleted.append(False)
            except KeyringError as e:
                raise KeyringStorageError(f"Failed to delete token from keyring: {e}") from e
            except Exception as e:
                raise KeyringStorageError(f"Failed to delete token from keyring: {e}") from e
            else:
                deleted.append(True)
        for candidate in dict.fromkeys((key, legacy_key)):
            try:
                if keyring.get_password(KEYRING_SERVICE, candidate):
                    return False
            except KeyringError as e:
                raise KeyringStorageError(f"Failed to verify token deletion: {e}") from e
            except Exception as e:
                raise KeyringStorageError(f"Failed to verify token deletion: {e}") from e
        return any(deleted)

    def list_accounts(self) -> list[str]:
        """List all stored accounts for this client.

        Note: This is a best-effort implementation. Some keyring backends
        don't support listing, so we also track accounts in config.

        Returns:
            List of account emails
        """
        config = self._config
        stored_accounts = config.get(f"accounts:{self.client}", [])
        return cast(list[str], stored_accounts)

    def add_account_to_list(self, account: str) -> None:
        """Add account to the tracked list."""
        config = self._config
        key = f"accounts:{self.client}"
        accounts = list(config.get(key, []))
        normalised = _normalise_account(account)
        if not any(_normalise_account(existing) == normalised for existing in accounts):
            accounts.append(account.strip())
            config.set(key, accounts)

    def remove_account_from_list(self, account: str) -> None:
        """Remove account from the tracked list."""
        config = self._config
        key = f"accounts:{self.client}"
        accounts = config.get(key, [])
        normalised = _normalise_account(account)
        remaining = [
            existing for existing in accounts if _normalise_account(existing) != normalised
        ]
        if len(remaining) != len(accounts):
            config.set(key, remaining)


class ServiceAccountDataError(KeyringDataError):
    """Raised when a service-account key in the keyring is corrupt or invalid."""


def _validate_service_account_data(key_data: Any) -> dict[str, Any]:
    """Validate the public shape required by google-auth service accounts."""
    if not isinstance(key_data, dict):
        raise ServiceAccountDataError("Stored service account data is not an object")
    if key_data.get("type") != "service_account":
        raise ServiceAccountDataError("Stored service account data has invalid type")
    for field in ("client_email", "private_key", "token_uri"):
        value = key_data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ServiceAccountDataError(
                f"Stored service account data requires a non-empty {field}"
            )
    return key_data


class ServiceAccountStorage:
    """Store service-account private material in the OS keyring only."""

    def __init__(self):
        self._config = get_config()
        backend = self._config.keyring_backend
        if isinstance(backend, str):
            configure_keyring_backend(backend)

    def _make_key(self, account: str) -> str:
        return f"{SERVICE_ACCOUNT_KEY_PREFIX}{_normalise_account(account)}"

    def _tracked_accounts(self) -> list[str]:
        accounts = self._config.get("service_accounts", [])
        if not isinstance(accounts, list) or not all(isinstance(item, str) for item in accounts):
            raise KeyringDataError("Stored service account index is invalid")
        return list(accounts)

    def _track(self, account: str) -> None:
        normalised = _normalise_account(account)
        accounts = self._tracked_accounts()
        if not any(_normalise_account(existing) == normalised for existing in accounts):
            accounts.append(normalised)
            self._config.set("service_accounts", accounts)

    def _untrack(self, account: str) -> None:
        normalised = _normalise_account(account)
        accounts = self._tracked_accounts()
        remaining = [
            existing for existing in accounts if _normalise_account(existing) != normalised
        ]
        if remaining != accounts:
            self._config.set("service_accounts", remaining)

    def store_key(self, account: str, key_data: dict[str, Any]) -> None:
        """Validate and store service-account credentials in the keyring."""
        validated = _validate_service_account_data(key_data)
        key = self._make_key(account)
        previous_value: str | None = None
        try:
            candidate = keyring.get_password(KEYRING_SERVICE, key)
            if isinstance(candidate, str):
                previous_value = candidate
        except KeyringError as exc:
            raise KeyringStorageError(
                f"Failed to inspect service account in keyring: {exc}"
            ) from exc
        try:
            value = json.dumps(validated)
            keyring.set_password(KEYRING_SERVICE, key, value)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise KeyringStorageError(
                f"Failed to serialize service account for keyring: {exc}"
            ) from exc
        except KeyringError as exc:
            raise KeyringStorageError(f"Failed to store service account in keyring: {exc}") from exc
        except Exception as exc:
            raise KeyringStorageError(f"Failed to store service account in keyring: {exc}") from exc
        try:
            self._track(account)
        except Exception:
            try:
                if previous_value is None:
                    keyring.delete_password(KEYRING_SERVICE, key)
                else:
                    keyring.set_password(KEYRING_SERVICE, key, previous_value)
            except Exception as rollback_error:
                raise KeyringStorageError(
                    f"Failed to update service account index and roll back keyring: {rollback_error}"
                ) from rollback_error
            raise

    def get_key(self, account: str) -> dict[str, Any] | None:
        """Load and validate service-account credentials from the keyring."""
        try:
            value = keyring.get_password(KEYRING_SERVICE, self._make_key(account))
        except KeyringError as exc:
            raise KeyringStorageError(
                f"Failed to read service account from keyring: {exc}"
            ) from exc
        except Exception as exc:
            raise KeyringStorageError(
                f"Failed to read service account from keyring: {exc}"
            ) from exc
        if not value:
            return None
        try:
            return _validate_service_account_data(json.loads(value))
        except ServiceAccountDataError:
            raise
        except (json.JSONDecodeError, TypeError) as exc:
            raise ServiceAccountDataError(
                f"Stored service account for '{account}' is corrupt JSON"
            ) from exc

    def delete_key(self, account: str) -> bool:
        """Delete keyring material and its non-secret account index entry."""
        key = self._make_key(account)
        previous_value: str | None = None
        try:
            candidate = keyring.get_password(KEYRING_SERVICE, key)
            if isinstance(candidate, str):
                previous_value = candidate
            keyring.delete_password(KEYRING_SERVICE, key)
        except PasswordDeleteError:
            return False
        except KeyringError as exc:
            raise KeyringStorageError(
                f"Failed to delete service account from keyring: {exc}"
            ) from exc
        except Exception as exc:
            raise KeyringStorageError(
                f"Failed to delete service account from keyring: {exc}"
            ) from exc
        try:
            self._untrack(account)
        except Exception:
            if previous_value is not None:
                try:
                    keyring.set_password(KEYRING_SERVICE, key, previous_value)
                except Exception as rollback_error:
                    raise KeyringStorageError(
                        f"Failed to update service account index and restore keyring: {rollback_error}"
                    ) from rollback_error
            raise
        return True

    def list_accounts(self) -> list[str]:
        """List non-secret service-account identifiers tracked in config."""
        return [_normalise_account(account) for account in self._tracked_accounts()]

    def has_key(self, account: str) -> bool:
        return self.get_key(account) is not None
