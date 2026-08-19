from unittest.mock import MagicMock

import pytest

from pygog.services.drive import DriveService


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.resolve_account.return_value = "test@example.com"
    config.get_client_for_account.return_value = "test-client"
    return config


@pytest.fixture
def drive_service(mock_config, monkeypatch):
    monkeypatch.setattr("pygog.services.base.get_config", lambda: mock_config)
    return DriveService(account="test@example.com")


def test_search_files_injection(drive_service):
    mock_drive_service = MagicMock()
    drive_service._service = mock_drive_service

    malicious_query = "foo' or name contains 'bar"
    drive_service.search_files(query=malicious_query)

    _, kwargs = mock_drive_service.files.return_value.list.call_args
    query = kwargs["q"]

    expected_query = "foo\\' or name contains \\'bar"
    assert f"'{expected_query}'" in query
    assert f"'{malicious_query}'" not in query


def test_list_files_injection(drive_service):
    mock_drive_service = MagicMock()
    drive_service._service = mock_drive_service

    malicious_parent = "foo' or 'bar' in parents"
    drive_service.list_files(parent_id=malicious_parent)

    _, kwargs = mock_drive_service.files.return_value.list.call_args
    query = kwargs["q"]

    expected_parent = "foo\\' or \\'bar\\' in parents"
    assert f"'{expected_parent}'" in query
    assert f"'{malicious_parent}'" not in query


def test_backslash_escaping(drive_service):
    mock_drive_service = MagicMock()
    drive_service._service = mock_drive_service

    drive_service.search_files(query="foo\\")

    _, kwargs = mock_drive_service.files.return_value.list.call_args
    query = kwargs["q"]

    expected_query = "foo\\\\"
    assert f"'{expected_query}'" in query


def test_backslash_quote_escaping(drive_service):
    mock_drive_service = MagicMock()
    drive_service._service = mock_drive_service

    drive_service.search_files(query="foo\\'")

    _, kwargs = mock_drive_service.files.return_value.list.call_args
    query = kwargs["q"]

    expected_query = "foo\\\\\\'"
    assert f"'{expected_query}'" in query
