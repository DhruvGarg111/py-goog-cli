"""OAuth credentials management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pygog.config import ensure_config_dir, get_config


def get_credentials_path(client: str = "default") -> Path:
    """Get the path to store credentials for a client."""
    config_dir = ensure_config_dir()
    if client == "default":
        return config_dir / "credentials.json"
    return config_dir / f"credentials-{client}.json"


class CredentialsManager:
    """Manages OAuth client credentials."""

    def __init__(self, client: str = "default"):
        """Initialize credentials manager.
        
        Args:
            client: OAuth client name
        """
        self.client = client
        self._path = get_credentials_path(client)

    def store(self, credentials_path: Path | str, domain: str | None = None) -> None:
        """Store OAuth client credentials from a file.
        
        Args:
            credentials_path: Path to the downloaded credentials JSON
            domain: Optional domain to associate with this client
        """
        source = Path(credentials_path)
        if not source.exists():
            raise FileNotFoundError(f"Credentials file not found: {source}")

        with open(source, encoding="utf-8") as f:
            data = json.load(f)

        # Validate it looks like OAuth credentials
        if "installed" not in data and "web" not in data:
            raise ValueError(
                "Invalid credentials file. Expected OAuth 2.0 client credentials "
                "(should contain 'installed' or 'web' key)"
            )

        # Store to config directory
        ensure_config_dir()
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Store domain mapping if provided
        if domain:
            config = get_config()
            client_domains = config.get("client_domains", {})
            client_domains[domain] = self.client
            config.set("client_domains", client_domains)

    def load(self) -> dict[str, Any] | None:
        """Load stored credentials.
        
        Returns:
            Credentials data or None if not found
        """
        if not self._path.exists():
            return None

        with open(self._path, encoding="utf-8") as f:
            return json.load(f)

    def exists(self) -> bool:
        """Check if credentials exist for this client."""
        return self._path.exists()

    def delete(self) -> bool:
        """Delete stored credentials.
        
        Returns:
            True if credentials were deleted
        """
        if self._path.exists():
            self._path.unlink()
            return True
        return False

    def get_client_config(self) -> dict[str, Any]:
        """Get the client configuration for OAuth flow.
        
        Returns:
            Client config dict with client_id, client_secret, etc.
        """
        data = self.load()
        if not data:
            raise FileNotFoundError(
                f"No credentials found for client '{self.client}'. "
                f"Run: pygog auth credentials <path-to-credentials.json>"
            )

        # Handle both 'installed' and 'web' credential types
        if "installed" in data:
            return data["installed"]
        elif "web" in data:
            return data["web"]
        else:
            raise ValueError("Invalid credentials format")

    @staticmethod
    def list_clients() -> list[dict[str, Any]]:
        """List all stored OAuth clients.
        
        Returns:
            List of dicts with client info
        """
        config_dir = ensure_config_dir()
        clients = []

        # Check for default credentials
        default_path = config_dir / "credentials.json"
        if default_path.exists():
            clients.append({
                "name": "default",
                "path": str(default_path),
            })

        # Check for named credentials
        for path in config_dir.glob("credentials-*.json"):
            name = path.stem.replace("credentials-", "")
            clients.append({
                "name": name,
                "path": str(path),
            })

        return clients
