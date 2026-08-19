import pytest

from pygog.services.drive import validate_remote_filename, validate_transfer_path


@pytest.mark.parametrize("name", ["../x", "a/b", "C:\\x", "CON", "/tmp/x"])
def test_remote_filename_must_be_safe_basename(name):
    with pytest.raises(ValueError):
        validate_remote_filename(name)


def test_existing_destination_requires_overwrite(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("old")
    with pytest.raises(FileExistsError):
        validate_transfer_path(target)
    assert target.read_text() == "old"
