"""Base service class for Google API wrappers."""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Iterator
from typing import Any, cast

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from pygog.auth.client import GoogleAuthClient
from pygog.config import get_config

TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})


def _status_from_error(error: BaseException) -> int | None:
    response = getattr(error, "resp", None)
    status = getattr(response, "status", None)
    if status is None:
        status = getattr(error, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def execute_with_retry(
    operation: Callable[[], Any],
    *,
    retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[float], float] | None = None,
) -> Any:
    """Execute a safe read, retrying documented transient Google statuses only."""
    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
        raise ValueError("retries must be a non-negative integer")
    if not isinstance(base_delay, (int, float)) or base_delay < 0:
        raise ValueError("base_delay must be non-negative")
    if not isinstance(max_delay, (int, float)) or max_delay < 0 or max_delay < base_delay:
        raise ValueError("max_delay must be non-negative and at least base_delay")
    jitter = jitter or (lambda delay: random.uniform(0, delay * 0.25))
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception as error:
            if _status_from_error(error) not in TRANSIENT_STATUSES or attempt >= retries:
                raise
            delay = min(max_delay, base_delay * (2**attempt))
            extra = jitter(delay)
            if not isinstance(extra, (int, float)) or extra < 0 or extra > delay:
                raise ValueError("jitter must return a value between zero and delay")
            sleep(delay + extra)
    raise AssertionError("unreachable")


def iter_pages(
    fetch: Callable[[str | None], dict[str, Any]],
    *,
    page_token: str | None = None,
    all_pages: bool = False,
    max_pages: int = 100,
) -> Iterator[dict[str, Any]]:
    """Yield bounded API response pages; callers decide how to merge wrappers."""
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise ValueError("max_pages must be a positive integer")
    token = page_token
    seen_tokens: set[str | None] = set()
    for _ in range(max_pages if all_pages else 1):
        if token in seen_tokens:
            return
        seen_tokens.add(token)
        response = fetch(token)
        yield response
        token = response.get("nextPageToken")
        if not all_pages or not token:
            return


class BaseService:
    """Base class for Google API service wrappers."""

    SERVICE_NAME: str = ""
    SERVICE_VERSION: str = ""

    def __init__(self, account: str | None = None, client: str | None = None):
        config = get_config()
        self._account = config.resolve_account(account)
        if not self._account:
            raise ValueError("No account specified. Use --account or set GOG_ACCOUNT.")
        self._client_name = (
            client if client is not None else config.get_client_for_account(self._account)
        )
        self._auth_client = GoogleAuthClient(self._client_name)
        self._service = None

    def _get_credentials(self) -> Credentials:
        creds = self._auth_client.get_credentials(cast(str, self._account))
        if not creds:
            raise ValueError(
                f"No credentials found for '{self._account}'. Run: pygog auth add {self._account}"
            )
        return creds

    def _get_service(self) -> Any:
        if self._service is None:
            creds = self._get_credentials()
            # googleapiclient.discovery.build has no supported timeout kwarg.
            # Per-request timeout must be configured on the underlying HTTP transport;
            # deliberately do not pass an invented timeout argument here.
            self._service = build(self.SERVICE_NAME, self.SERVICE_VERSION, credentials=creds)
        return self._service

    @staticmethod
    def _execute(request: Any) -> dict[str, Any]:
        """Execute an idempotent Google read with bounded transient retries."""
        return cast(dict[str, Any], execute_with_retry(request.execute))

    @property
    def account(self) -> str:
        return cast(str, self._account)
