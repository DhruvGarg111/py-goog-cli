"""OAuth2 authentication client for Google APIs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from pygog.auth.credentials import CredentialsManager
from pygog.auth.keyring import KeyringStorage, ServiceAccountStorage, _normalise_account


def verify_oauth2_token(raw_token: str, request: Request, audience: str | None = None):
    """Delegate ID-token verification through the installed google-auth API."""
    return id_token.verify_oauth2_token(raw_token, request, audience=audience)


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

DEFAULT_SERVICES = ["gmail", "calendar", "drive", "tasks"]

READONLY_SERVICE_SCOPES = {
    "gmail": ["https://www.googleapis.com/auth/gmail.readonly"],
    "calendar": ["https://www.googleapis.com/auth/calendar.readonly"],
    "drive": ["https://www.googleapis.com/auth/drive.readonly"],
    "tasks": ["https://www.googleapis.com/auth/tasks.readonly"],
}

READONLY_SCOPES = {
    "https://www.googleapis.com/auth/gmail.modify": "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar": "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive": "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/tasks": "https://www.googleapis.com/auth/tasks.readonly",
    "https://www.googleapis.com/auth/spreadsheets": "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/contacts": "https://www.googleapis.com/auth/contacts.readonly",
}


class AuthenticationError(RuntimeError):
    """Raised when stored or newly-issued OAuth credentials cannot be trusted."""


def _aware_utc(value: datetime) -> datetime:
    """Return a credential expiry as an aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class _StoredCredentials(Credentials):
    """Credentials with explicit expiry semantics for keyring-loaded tokens."""

    @property
    def expired(self) -> bool:
        # A missing expiry must never be treated as an indefinitely valid token.
        if self.expiry is None:
            return True
        return datetime.now(timezone.utc) >= (_aware_utc(self.expiry) - timedelta(minutes=5))


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
    requested_services = DEFAULT_SERVICES if services is None else services
    expanded_services = []
    for requested_service in requested_services:
        service = requested_service.strip().lower()
        if service in {"user", "all"}:
            expanded_services.extend(DEFAULT_SERVICES)
        elif service not in SCOPES:
            raise ValueError(f"Unknown service '{requested_service}'.")
        else:
            expanded_services.append(service)

    if readonly:
        unsupported = sorted(
            {service for service in expanded_services if service not in READONLY_SERVICE_SCOPES}
        )
        if unsupported:
            services_text = ", ".join(unsupported)
            raise ValueError(f"No read-only scopes are defined for service(s): {services_text}.")
        scopes = {
            scope for service in expanded_services for scope in READONLY_SERVICE_SCOPES[service]
        }
    else:
        scopes = {scope for service in expanded_services for scope in SCOPES[service]}

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

    @staticmethod
    def _parse_expiry(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        raw_expiry = str(value).strip()
        if raw_expiry.endswith("Z"):
            raw_expiry = raw_expiry[:-1]
        return datetime.fromisoformat(raw_expiry)

    @classmethod
    def _normalise_authorized_user_info(cls, token_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize expiry input to the format accepted by google-auth."""
        info = dict(token_data)
        info.setdefault("refresh_token", None)
        expiry = info.get("expiry")
        if expiry:
            parsed = cls._parse_expiry(expiry)
            info["expiry"] = (
                _aware_utc(parsed).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
            )
        return info

    @classmethod
    def _credentials_from_token_data(cls, token_data: dict[str, Any]) -> _StoredCredentials:
        """Reconstruct credentials through Google's authorized-user contract."""
        try:
            original_expiry = token_data.get("expiry")
            info = cls._normalise_authorized_user_info(token_data)
            credentials = _StoredCredentials.from_authorized_user_info(info)
            if original_expiry:
                credentials.expiry = _aware_utc(cls._parse_expiry(original_expiry))
        except (KeyError, TypeError, ValueError) as e:
            raise AuthenticationError(
                "Stored OAuth credentials are invalid. Re-authenticate the account."
            ) from e

        # google-auth currently returns a naive UTC datetime from this contract.
        # Keep the public credential expiry unambiguously timezone-aware.
        if credentials.expiry is None:
            credentials.expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
        else:
            credentials.expiry = _aware_utc(credentials.expiry)
        return cast(_StoredCredentials, credentials)

    @staticmethod
    def _serialize_credentials(
        credentials: Credentials,
        scopes: list[str],
        refresh_token: str | None = None,
        verified_account: str | None = None,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        """Serialize credentials using Google's authorized-user JSON contract."""
        try:
            token_data = json.loads(credentials.to_json())
        except (AttributeError, TypeError, ValueError):
            token_data = {}

        token_data.setdefault("token", credentials.token)
        token_data.setdefault("refresh_token", getattr(credentials, "refresh_token", None))
        token_data.setdefault(
            "token_uri",
            getattr(credentials, "token_uri", None) or "https://oauth2.googleapis.com/token",
        )
        token_data.setdefault("client_id", getattr(credentials, "client_id", None))
        token_data.setdefault("client_secret", getattr(credentials, "client_secret", None))
        if client_id:
            token_data["client_id"] = client_id
        credential_scopes = getattr(credentials, "scopes", None)
        token_data.setdefault("scopes", list(credential_scopes) if credential_scopes else scopes)

        if not token_data.get("refresh_token") and refresh_token:
            token_data["refresh_token"] = refresh_token

        if credentials.expiry is not None:
            token_data["expiry"] = (
                _aware_utc(credentials.expiry).replace(tzinfo=None).isoformat() + "Z"
            )
        elif "expiry" not in token_data:
            token_data.pop("expiry", None)

        if verified_account:
            token_data["account"] = verified_account
            token_data["verified_account"] = verified_account
        return cast(dict[str, Any], token_data)

    @staticmethod
    def _authenticated_email(credentials: Credentials, audience: str | None) -> str:
        """Verify the flow's OIDC identity and return its canonical email."""
        if not isinstance(audience, str) or not audience.strip():
            raise AuthenticationError(
                "OAuth client ID is missing from the trusted configuration; refusing "
                "unbound identity verification."
            )
        raw_id_token = getattr(credentials, "id_token", None)
        if not raw_id_token:
            raise AuthenticationError(
                "Google did not return a verifiable identity. Re-authenticate and grant "
                "the openid and email scopes."
            )
        try:
            claims = verify_oauth2_token(raw_id_token, Request(), audience=audience)
        except Exception as e:
            raise AuthenticationError(
                "Google identity verification failed. Re-authenticate the account."
            ) from e

        if not isinstance(claims, Mapping):
            raise AuthenticationError(
                "Google returned malformed identity claims. Re-authenticate the account."
            )
        email = claims.get("email")
        email = str(email).strip() if email else ""
        if not email or claims.get("email_verified") is not True:
            raise AuthenticationError(
                "Google returned an unverified identity. Re-authenticate the account."
            )
        return email

    @staticmethod
    def _validate_stored_provenance(token_data: Mapping[str, Any], requested_account: str) -> None:
        """Reject stored identity metadata that belongs to another account."""
        normalised_requested = _normalise_account(requested_account)
        for field in ("account", "verified_account"):
            metadata = token_data.get(field)
            if metadata is None:
                continue
            if isinstance(metadata, str) and not metadata.strip():
                # google-auth's legacy JSON serializer emits account="".
                continue
            if not isinstance(metadata, str):
                raise AuthenticationError(
                    "Stored OAuth credentials have invalid account provenance."
                )
            if _normalise_account(metadata) != normalised_requested:
                raise AuthenticationError(
                    "Stored OAuth credentials have mismatched account provenance."
                )

    def _oauth_credentials(self, account: str) -> tuple[_StoredCredentials | None, bool]:
        """Load OAuth credentials, refreshing and persisting them when needed."""
        token_data = self._keyring.get_token(account)
        if not token_data:
            return None, False

        self._validate_stored_provenance(token_data, account)
        credentials = self._credentials_from_token_data(token_data)
        if credentials.valid or not credentials.refresh_token:
            return credentials, False

        try:
            credentials.refresh(Request())
        except Exception as e:
            raise AuthenticationError(
                f"Unable to refresh credentials for '{account}'. "
                f"Please re-authenticate with `pygog auth add {account}`."
            ) from e

        if credentials.expiry is None:
            raise AuthenticationError(
                f"Google returned no expiry while refreshing '{account}'. "
                f"Please re-authenticate with `pygog auth add {account}`."
            )
        credentials.expiry = _aware_utc(credentials.expiry)
        refreshed_data = self._serialize_credentials(
            credentials,
            scopes=list(credentials.scopes) if credentials.scopes else token_data.get("scopes", []),
            refresh_token=token_data.get("refresh_token"),
            verified_account=token_data.get("verified_account") or token_data.get("account"),
        )
        self._keyring.store_token(account, refreshed_data)
        return credentials, True

    def authorize(
        self,
        account: str,
        services: list[str] | None = None,
        readonly: bool = False,
        force_consent: bool = False,
    ) -> Credentials:
        """Run OAuth authorization flow for an account."""
        scopes = sorted(set(get_scopes_for_services(services, readonly) + ["openid", "email"]))
        client_config = self._credentials_manager.get_client_config()
        trusted_client_id = client_config.get("client_id")
        if not isinstance(trusted_client_id, str) or not trusted_client_id.strip():
            raise AuthenticationError(
                "OAuth client ID is missing from the trusted configuration; refusing "
                "to authorize an unbound identity."
            )
        trusted_client_id = trusted_client_id.strip()
        requested_account = _normalise_account(account)
        previous_token = self._keyring.get_token(account)

        flow = InstalledAppFlow.from_client_config(
            {"installed": client_config},
            scopes=scopes,
        )

        run_kwargs = {
            "port": 0,
            "authorization_prompt_message": "Opening browser for authorization...",
            "success_message": "Authorization successful! You can close this window.",
            "open_browser": True,
            "login_hint": requested_account,
        }
        if force_consent:
            run_kwargs["prompt"] = "consent"

        try:
            credentials = flow.run_local_server(**run_kwargs)
        except Exception as e:
            raise RuntimeError(f"Authorization failed: {e}") from e

        authenticated_email = self._authenticated_email(
            credentials,
            audience=trusted_client_id,
        )
        authenticated_account = _normalise_account(authenticated_email)
        if authenticated_account != requested_account:
            raise AuthenticationError(
                f"Authenticated as a different account ('{authenticated_email}') than "
                f"requested ('{account}'). Re-authenticate the requested account."
            )
        if credentials.expiry is None:
            raise AuthenticationError(
                f"Google returned no token expiry for '{authenticated_email}'. "
                f"Please re-authenticate with `pygog auth add {account}`."
            )

        preserved_refresh_token = None
        if previous_token is not None and self._can_preserve_refresh_token(
            previous_token,
            trusted_client_id,
            authenticated_account,
        ):
            refresh_token = previous_token.get("refresh_token")
            if isinstance(refresh_token, str):
                preserved_refresh_token = refresh_token

        token_data = self._serialize_credentials(
            credentials,
            scopes=scopes,
            refresh_token=preserved_refresh_token,
            verified_account=authenticated_account,
            client_id=trusted_client_id,
        )
        self._keyring.store_token(authenticated_account, token_data)
        self._keyring.add_account_to_list(authenticated_account)

        return cast(Credentials, credentials)

    def get_credentials(self, account: str) -> Credentials | None:
        """Get stored credentials for an account, refreshing them when expired."""
        normalised_account = _normalise_account(account)
        sa_key = self._service_accounts.get_key(normalised_account)
        if sa_key is not None:
            from google.oauth2 import service_account

            return cast(
                Credentials,
                service_account.Credentials.from_service_account_info(
                    sa_key,
                    subject=normalised_account,
                ),
            )

        credentials, _ = self._oauth_credentials(account)
        return credentials

    def remove_account(self, account: str) -> bool:
        """Remove stored credentials for an account.

        Args:
            account: Account email

        Returns:
            True if account was removed
        """
        normalised_account = _normalise_account(account)
        if self._service_accounts.get_key(normalised_account) is not None:
            if not self._service_accounts.delete_key(normalised_account):
                return False
            if self._service_accounts.get_key(normalised_account) is not None:
                return False
            self._keyring.remove_account_from_list(normalised_account)
            return True

        if not self._keyring.delete_token(account):
            return False
        if self._keyring.get_token(account) is not None:
            return False
        self._keyring.remove_account_from_list(normalised_account)
        return True

    def list_accounts(self) -> list[dict[str, Any]]:
        """List all stored accounts.

        Returns:
            List of account info dicts
        """
        try:
            oauth_accounts = self._keyring.list_accounts()
        except Exception:
            oauth_accounts = []
        service_accounts = self._service_accounts.list_accounts()
        account_names = []
        seen = set()
        for email in [*oauth_accounts, *service_accounts]:
            normalised = _normalise_account(email)
            if normalised not in seen:
                seen.add(normalised)
                account_names.append(normalised)

        accounts = []
        for email in account_names:
            has_sa = self._service_accounts.has_key(email)
            has_token = False
            if not has_sa:
                try:
                    has_token = self._keyring.get_token(email) is not None
                except Exception:
                    has_token = False
            accounts.append(
                {
                    "email": email,
                    "client": self.client,
                    "auth_type": "service_account" if has_sa else "oauth",
                    "has_token": has_token,
                }
            )
        return accounts

    def check_token(self, account: str) -> dict[str, Any]:
        """Check if a token is valid.

        Args:
            account: Account email

        Returns:
            Status dict with valid, expired, scopes
        """
        if self._service_accounts.get_key(account) is not None:
            credentials = self.get_credentials(account)
            refreshed = False
        else:
            credentials, refreshed = self._oauth_credentials(account)
        if not credentials:
            return {"valid": False, "error": "No token found"}

        if not credentials.valid:
            return {"valid": False, "error": "Token missing or expired, no refresh token"}

        status = {
            "valid": True,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
        }
        if refreshed:
            status["refreshed"] = True
        return status

    @staticmethod
    def _can_preserve_refresh_token(
        previous_token: Mapping[str, Any] | None,
        trusted_client_id: str,
        authenticated_account: str,
    ) -> bool:
        """Allow refresh-token reuse only for the same trusted identity context."""
        if not isinstance(previous_token, Mapping):
            return False
        refresh_token = previous_token.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return False
        if previous_token.get("client_id") != trusted_client_id:
            return False
        verified_account = previous_token.get("verified_account")
        if not isinstance(verified_account, str):
            return False
        if _normalise_account(verified_account) != authenticated_account:
            return False
        stored_account = previous_token.get("account")
        return stored_account is None or (
            isinstance(stored_account, str)
            and _normalise_account(stored_account) == authenticated_account
        )
