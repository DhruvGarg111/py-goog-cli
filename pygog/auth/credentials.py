"""Secure OAuth client credential management."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

from pygog.config import atomic_write_json, ensure_config_dir, get_config

_CLIENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_REQUIRED_CLIENT_FIELDS = ("client_id", "client_secret", "auth_uri", "token_uri")


class CredentialsError(ValueError):
    """Raised when OAuth client credentials are missing, malformed, or unsafe."""


def _validate_client_config(config: Any, *, source: str) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise CredentialsError(
            f"Invalid credentials file ({source}): OAuth client config must be an object"
        )
    for field in _REQUIRED_CLIENT_FIELDS:
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CredentialsError(
                f"Invalid credentials file ({source}): missing non-empty '{field}'"
            )
    redirect_uris = config.get("redirect_uris")
    if redirect_uris is not None and (
        not isinstance(redirect_uris, list)
        or not all(isinstance(uri, str) and uri.strip() for uri in redirect_uris)
    ):
        raise CredentialsError(
            f"Invalid credentials file ({source}): 'redirect_uris' must be a list of strings"
        )
    return config


def _validate_credentials_document(data: Any, *, source: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise CredentialsError(f"Invalid credentials file ({source}): top level must be an object")
    sections = [name for name in ("installed", "web") if name in data]
    if not sections:
        raise CredentialsError(
            f"Invalid credentials file ({source}): expected 'installed' or 'web' key"
        )
    for section in sections:
        _validate_client_config(data[section], source=source)
    return data


def _load_json(path: Path, *, source: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CredentialsError(f"Unable to read {source} credentials: {exc}") from exc
    return _validate_credentials_document(data, source=source)


def get_credentials_path(client: str = "default") -> Path:
    """Get the private path used to store credentials for a client."""
    if not isinstance(client, str) or not _CLIENT_RE.fullmatch(client):
        raise CredentialsError(
            "OAuth client name must contain only letters, numbers, '.', '_' or '-'"
        )
    config_dir = ensure_config_dir()
    if client == "default":
        return config_dir / "credentials.json"
    return config_dir / f"credentials-{client}.json"


class CredentialsManager:
    """Manage validated OAuth client credentials with private atomic writes."""

    def __init__(self, client: str = "default"):
        self.client = client
        self._path = get_credentials_path(client)

    def store(self, credentials_path: Path | str, domain: str | None = None) -> None:
        """Validate and securely store downloaded OAuth client credentials."""
        source = Path(credentials_path)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Credentials file not found: {source}")

        data = _load_json(source, source=str(source))
        if domain is not None:
            if (
                not isinstance(domain, str)
                or not domain.strip()
                or domain != domain.strip()
                or any(character.isspace() for character in domain)
                or "@" in domain
            ):
                raise CredentialsError("Credential domain must be a non-empty DNS name")
        try:
            atomic_write_json(self._path, data, mode=0o600)
        except Exception as exc:
            if isinstance(exc, CredentialsError):
                raise
            raise CredentialsError(
                f"Unable to store credentials for client '{self.client}': {exc}"
            ) from exc

        if domain is not None:
            config = get_config()
            client_domains = config.get("client_domains", {})
            if not isinstance(client_domains, dict):
                raise CredentialsError("client_domains configuration is invalid")
            updated_domains = dict(client_domains)
            updated_domains[domain.strip().casefold()] = self.client
            config.set("client_domains", updated_domains)

    def load(self) -> dict[str, Any] | None:
        """Load and validate stored credentials, or return None when absent."""
        if not self._path.exists():
            return None
        return _load_json(self._path, source="stored")

    def exists(self) -> bool:
        """Check if credentials exist for this client."""
        return self._path.exists()

    def delete(self) -> bool:
        """Delete stored credentials."""
        if self._path.exists():
            self._path.unlink()
            return True
        return False

    def get_client_config(self) -> dict[str, Any]:
        """Get the client configuration for the OAuth flow."""
        data = self.load()
        if not data:
            raise FileNotFoundError(
                f"No credentials found for client '{self.client}'. "
                f"Run: pygog auth credentials <path-to-credentials.json>"
            )

        if "installed" in data:
            return cast(dict[str, Any], data["installed"])
        if "web" in data:
            return cast(dict[str, Any], data["web"])
        # _validate_credentials_document makes this unreachable, but keeping a
        # typed guard here protects callers if the format is extended later.
        raise CredentialsError("Invalid credentials format")

    @staticmethod
    def list_clients() -> list[dict[str, Any]]:
        """List stored OAuth client names and their local paths."""
        config_dir = ensure_config_dir()
        clients = []

        default_path = config_dir / "credentials.json"
        if default_path.exists():
            clients.append({"name": "default", "path": str(default_path)})

        for path in config_dir.glob("credentials-*.json"):
            name = path.stem.replace("credentials-", "", 1)
            if _CLIENT_RE.fullmatch(name):
                clients.append({"name": name, "path": str(path)})

        return clients


__all__ = ["CredentialsError", "CredentialsManager", "get_credentials_path"]
