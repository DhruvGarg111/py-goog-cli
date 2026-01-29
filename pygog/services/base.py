"""Base service class for Google API wrappers."""

from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from pygog.auth.client import GoogleAuthClient
from pygog.config import get_config


class BaseService:
    """Base class for Google API service wrappers."""

    # Override in subclasses
    SERVICE_NAME: str = ""
    SERVICE_VERSION: str = ""

    def __init__(self, account: str | None = None, client: str | None = None):
        """Initialize the service.
        
        Args:
            account: Account email (uses default if None)
            client: OAuth client name (uses default if None)
        """
        config = get_config()
        self._account = config.resolve_account(account)
        if not self._account:
            raise ValueError(
                "No account specified. Use --account or set GOG_ACCOUNT."
            )
        
        self._client_name = client or config.get_client_for_account(self._account)
        self._auth_client = GoogleAuthClient(self._client_name)
        self._service = None

    def _get_credentials(self) -> Credentials:
        """Get credentials for the account."""
        creds = self._auth_client.get_credentials(self._account)
        if not creds:
            raise ValueError(
                f"No credentials found for '{self._account}'. "
                f"Run: pygog auth add {self._account}"
            )
        return creds

    def _get_service(self) -> Any:
        """Get or create the API service."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build(
                self.SERVICE_NAME,
                self.SERVICE_VERSION,
                credentials=creds,
            )
        return self._service

    @property
    def account(self) -> str:
        """Get the account email."""
        return self._account
