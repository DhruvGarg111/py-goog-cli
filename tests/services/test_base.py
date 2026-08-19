import pytest

from pygog.services.base import execute_with_retry, iter_pages


def test_retry_retries_only_transient_statuses_with_injected_sleep():
    attempts = []
    sleeps = []

    class Error(Exception):
        def __init__(self, status):
            self.resp = type("Resp", (), {"status": status})()

    def operation():
        attempts.append(1)
        if len(attempts) < 3:
            raise Error(503)
        return "ok"

    assert execute_with_retry(operation, sleep=sleeps.append, jitter=lambda _: 0) == "ok"
    assert len(attempts) == 3
    assert sleeps == [0.5, 1.0]


def test_retry_does_not_retry_permanent_client_error():
    attempts = []

    class Error(Exception):
        resp = type("Resp", (), {"status": 400})()

    def operation():
        attempts.append(1)
        raise Error()

    with pytest.raises(Error):
        execute_with_retry(operation, sleep=lambda _: None)
    assert len(attempts) == 1


def test_iter_pages_is_bounded_and_preserves_page_tokens():
    calls = []

    def fetch(token):
        calls.append(token)
        return {"items": [token or "first"], "nextPageToken": "next" if token is None else None}

    assert list(iter_pages(fetch, page_token="start", all_pages=False)) == [
        {"items": ["start"], "nextPageToken": None}
    ]
    assert calls == ["start"]
