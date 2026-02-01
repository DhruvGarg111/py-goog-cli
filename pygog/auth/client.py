"""OAuth2 authentication client for Google APIs."""

from __future__ import annotations

import webbrowser
from typing import Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from pygog.config import get_config
from pygog.auth.credentials import CredentialsManager
from pygog.auth.keyring import KeyringStorage, ServiceAccountStorage

SCOPES = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.settings.basic",
    ],
    "calendar": [
        "https://www.googleapis.com/auth/calendar",
    ],
    "drive": [
        "https://www.googleapis.com/auth/drive",
    ],
    "tasks": [
        "https://www.googleapis.com/auth/tasks",
    ],
    "sheets": [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
    "docs": [
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/drive",
    ],
    "contacts": [
        "https://www.googleapis.com/auth/contacts",
        "https://www.googleapis.com/auth/directory.readonly",
    ],
    "chat": [
        "https://www.googleapis.com/auth/chat.spaces",
        "https://www.googleapis.com/auth/chat.messages",
    ],
    "classroom": [
        "https://www.googleapis.com/auth/classroom.courses",
        "https://www.googleapis.com/auth/classroom.rosters",
    ],
    "groups": [
        "https://www.googleapis.com/auth/cloud-identity.groups.readonly",
    ],
    "keep": [
        "https://www.googleapis.com/auth/keep.readonly",
    ],
    "people": [
        "profile",
    ],
}

DEFAULT_SERVICES = ["gmail", "calendar", "drive", "tasks", "contacts", "people"]

READONLY_SCOPES = {
    "https://www.googleapis.com/auth/gmail.modify": "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar": "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive": "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/tasks": "https://www.googleapis.com/auth/tasks.readonly",
    "https://www.googleapis.com/auth/spreadsheets": "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/contacts": "https://www.googleapis.com/auth/contacts.readonly",
}


def get_scopes_for_services(
    services: list[str] | None = None,
    readonly: bool = False,
) -> list[str]:
    """Get OAuth scopes for requested services.
    
    Args:
        services: List of service names (defaults to DEFAULT_SERVICES)
        readonly: If True, use read-only scopes where available
        
    Returns:
        List of OAuth scope URLs
    """
    if services is None:
        services = DEFAULT_SERVICES

    scopes = set()
    for service in services:
        service = service.lower()
        if service == "user" or service == "all":
            for svc in DEFAULT_SERVICES:
                scopes.update(SCOPES.get(svc, []))
        elif service in SCOPES:
            scopes.update(SCOPES[service])

    if readonly:
        scopes = {READONLY_SCOPES.get(s, s) for s in scopes}

    return sorted(scopes)


class GoogleAuthClient:
    """OAuth2 authentication client for Google APIs."""

    def __init__(self, client: str = "default"):
        """Initialize auth client.
        
        Args:
            client: OAuth client name
        """
        self.client = client
        self._credentials_manager = CredentialsManager(client)
        self._keyring = KeyringStorage(client)
        self._service_accounts = ServiceAccountStorage()

    def authorize(
        self,
        account: str,
        services: list[str] | None = None,
        readonly: bool = False,
        force_consent: bool = False,
    ) -> Credentials:
        """Run OAuth authorization flow for an account.
        
        Args:
            account: Account email (hint for Google)
            services: List of services to request scopes for
            readonly: Request read-only scopes
            force_consent: Force consent screen even if already authorized
            
        Returns:
            Credentials object
        """
        scopes = get_scopes_for_services(services, readonly)
        client_config = self._credentials_manager.get_client_config()

        flow = InstalledAppFlow.from_client_config(
            {"installed": client_config},
            scopes=scopes,
        )

        try:
            credentials = flow.run_local_server(
                port=0,
                authorization_prompt_message="Opening browser for authorization...",
                success_message="Authorization successful! You can close this window.",
                open_browser=True,
                login_hint=account,
            )
        except Exception as e:
            raise RuntimeError(f"Authorization failed: {e}") from e

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else scopes,
        }
        self._keyring.store_token(account, token_data)
        self._keyring.add_account_to_list(account)

        return credentials

    def get_credentials(self, account: str) -> Credentials | None:
        """Get stored credentials for an account.
        
        Args:
            account: Account email
            
        Returns:
            Credentials object or None if not found
        """
        sa_key = self._service_accounts.get_key(account)
        if sa_key:
            from google.oauth2 import service_account
            return service_account.Credentials.from_service_account_info(
                sa_key,
                subject=account,
            )

        token_data = self._keyring.get_token(account)
        if not token_data:
            return None

        credentials = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )

        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                token_data["token"] = credentials.token
                self._keyring.store_token(account, token_data)
            except Exception:
                pass

        return credentials

    def remove_account(self, account: str) -> bool:
        """Remove stored credentials for an account.
        
        Args:
            account: Account email
            
        Returns:
            True if account was removed
        """
        self._keyring.delete_token(account)
        self._keyring.remove_account_from_list(account)
        return True

    def list_accounts(self) -> list[dict[str, Any]]:
        """List all stored accounts.
        
        Returns:
            List of account info dicts
        """
        accounts = []
        for email in self._keyring.list_accounts():
            has_sa = self._service_accounts.has_key(email)
            has_token = self._keyring.get_token(email) is not None
            accounts.append({
                "email": email,
                "client": self.client,
                "auth_type": "service_account" if has_sa else "oauth",
                "has_token": has_token,
            })
        return accounts

    def check_token(self, account: str) -> dict[str, Any]:
        """Check if a token is valid.
        
        Args:
            account: Account email
            
        Returns:
            Status dict with valid, expired, scopes
        """
        credentials = self.get_credentials(account)
        if not credentials:
            return {"valid": False, "error": "No token found"}

        if credentials.expired:
            if credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    return {
                        "valid": True,
                        "refreshed": True,
                        "scopes": list(credentials.scopes) if credentials.scopes else [],
                    }
                except Exception as e:
                    return {"valid": False, "error": str(e)}
            return {"valid": False, "error": "Token expired, no refresh token"}

        return {
            "valid": True,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }
