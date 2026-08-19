from unittest.mock import patch

import pygog.agent.tools as agent_tools


class FakeDriveService:
    def __init__(self, *, list_response=None, search_response=None):
        self.list_response = list_response if list_response is not None else {}
        self.search_response = search_response if search_response is not None else {}
        self.list_calls = []
        self.search_calls = []

    def list_files(self, **kwargs):
        self.list_calls.append(kwargs)
        return self.list_response

    def search_files(self, **kwargs):
        self.search_calls.append(kwargs)
        return self.search_response


def test_drive_list_passes_folder_id_and_normalizes_response():
    service = FakeDriveService(
        list_response={
            "files": [
                {
                    "id": "folder-1",
                    "name": "Projects",
                    "mimeType": "application/vnd.google-apps.folder",
                    "modifiedTime": "2026-08-19T10:00:00Z",
                },
                {
                    "id": "file-1",
                    "name": "plan.txt",
                    "mimeType": "text/plain",
                    "modifiedTime": "2026-08-18T09:00:00Z",
                },
            ]
        }
    )

    with patch("pygog.services.drive.DriveService", return_value=service) as drive_service:
        result = agent_tools.drive_list(
            folder_id="folder-1", max_results=2, account="user@example.com"
        )

    drive_service.assert_called_once_with(account="user@example.com")
    assert service.list_calls == [{"parent_id": "folder-1", "max_results": 2}]
    assert result == [
        {
            "id": "folder-1",
            "name": "Projects",
            "type": "folder",
            "mime_type": "application/vnd.google-apps.folder",
            "modified": "2026-08-19T10:00:00Z",
        },
        {
            "id": "file-1",
            "name": "plan.txt",
            "type": "file",
            "mime_type": "text/plain",
            "modified": "2026-08-18T09:00:00Z",
        },
    ]


def test_drive_list_returns_empty_list_for_empty_or_missing_files():
    for response in ({"files": []}, {}):
        service = FakeDriveService(list_response=response)

        with patch("pygog.services.drive.DriveService", return_value=service):
            result = agent_tools.drive_list(folder_id=None, max_results=5)

        assert service.list_calls == [{"parent_id": None, "max_results": 5}]
        assert result == []


def test_drive_search_passes_plain_term_and_normalizes_response():
    service = FakeDriveService(
        search_response={
            "files": [
                {
                    "id": "file-2",
                    "name": "quarterly report.pdf",
                    "mimeType": "application/pdf",
                    "webViewLink": "https://drive.google.com/file/d/file-2/view",
                }
            ]
        }
    )

    with patch("pygog.services.drive.DriveService", return_value=service):
        result = agent_tools.drive_search(
            query="quarterly report", max_results=3, account="user@example.com"
        )

    assert service.search_calls == [{"query": "quarterly report", "max_results": 3}]
    assert result == [
        {
            "id": "file-2",
            "name": "quarterly report.pdf",
            "type": "file",
            "mime_type": "application/pdf",
            "web_link": "https://drive.google.com/file/d/file-2/view",
        }
    ]


def test_drive_search_returns_empty_list_for_empty_or_missing_files():
    for response in ({"files": []}, {}):
        service = FakeDriveService(search_response=response)

        with patch("pygog.services.drive.DriveService", return_value=service):
            result = agent_tools.drive_search(query="report", max_results=5)

        assert service.search_calls == [{"query": "report", "max_results": 5}]
        assert result == []
