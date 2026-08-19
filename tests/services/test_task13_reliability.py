import pytest

from pygog.services.base import execute_with_retry, iter_pages
from pygog.services.drive import DriveService
from pygog.services.gmail import GmailService
from pygog.services.tasks import TasksService


class Request:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def execute(self):
        self.calls += 1
        return self.value


class Resource:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def list(self, **params):
        token = params.get("pageToken")
        self.calls.append(params)
        return Request(self.pages[token])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"retries": -1},
        {"retries": 1.5},
        {"base_delay": -1},
        {"max_delay": -1},
        {"base_delay": 2, "max_delay": 1},
    ],
)
def test_retry_rejects_invalid_bounds(kwargs):
    with pytest.raises(ValueError):
        execute_with_retry(lambda: None, **kwargs)


def test_iter_pages_stops_on_repeated_token():
    calls = []

    def fetch(token):
        calls.append(token)
        return {"items": [], "nextPageToken": "same"}

    assert len(list(iter_pages(fetch, all_pages=True, max_pages=10))) == 2
    assert calls == [None, "same"]


def test_gmail_all_search_is_bounded_and_retries_later_pages():
    service = GmailService.__new__(GmailService)
    resource = Resource(
        {
            None: {"threads": [{"id": "1"}], "nextPageToken": "next"},
            "next": {"threads": [{"id": "2"}], "nextPageToken": "next"},
        }
    )
    service._users = lambda: type("Users", (), {"threads": lambda self: resource})()

    result = service.search_threads("q", all_pages=True)

    assert [item["id"] for item in result["threads"]] == ["1", "2"]
    assert len(resource.calls) == 2


def test_tasks_all_list_is_bounded_on_repeated_token():
    service = TasksService.__new__(TasksService)
    resource = Resource(
        {
            None: {"items": [{"id": "1"}], "nextPageToken": "same"},
            "same": {"items": [{"id": "2"}], "nextPageToken": "same"},
        }
    )
    service._tasks = lambda: resource

    assert [item["id"] for item in service.list_tasks("list", all_pages=True)] == ["1", "2"]
    assert len(resource.calls) == 2


def test_drive_read_requests_include_shared_drive_parameters(monkeypatch):
    service = DriveService.__new__(DriveService)
    calls = []
    files = type("Files", (), {})()
    files.get = lambda **kwargs: (
        calls.append(("get", kwargs)) or Request({"mimeType": "application/pdf"})
    )
    files.export_media = lambda **kwargs: calls.append(("export", kwargs)) or Request({})
    service._files = lambda: files
    monkeypatch.setattr(DriveService, "_transfer", staticmethod(lambda *args, **kwargs: None))

    service.get_file("file")
    service.export_file("file", "pdf", "/tmp/out.pdf")

    assert calls[0][1]["supportsAllDrives"] is True
    assert calls[1][1]["supportsAllDrives"] is True


def test_transfer_failure_removes_reserved_destination(tmp_path):
    destination = tmp_path / "out.bin"

    class Downloader:
        def __init__(self, handle, request):
            pass

        def next_chunk(self):
            raise RuntimeError("download failed")

    import pygog.services.drive as drive

    original = drive.MediaIoBaseDownload
    drive.MediaIoBaseDownload = Downloader
    try:
        with pytest.raises(RuntimeError):
            DriveService._transfer(object(), destination, overwrite=False)
    finally:
        drive.MediaIoBaseDownload = original

    assert not destination.exists()


def test_export_validates_destination_before_metadata_lookup(tmp_path):
    service = DriveService.__new__(DriveService)
    service.get_file = lambda file_id: pytest.fail("metadata lookup happened too early")
    with pytest.raises(FileExistsError):
        target = tmp_path / "existing.pdf"
        target.write_text("keep")
        service.export_file("file", "pdf", target)
