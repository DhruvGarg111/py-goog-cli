
import pytest
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from pygog.commands.drive import app
from pygog.cli import state

runner = CliRunner()

@pytest.fixture(autouse=True)
def mock_state():
    state.json_output = False
    state.plain_output = False
    state.force = False
    yield
    state.json_output = False
    state.plain_output = False
    state.force = False

@patch("pygog.commands.drive.get_service")
def test_rename_dry_run(mock_get_service):
    result = runner.invoke(app, ["rename", "123", "new_name.txt", "--dry-run"])
    assert result.exit_code == 0
    assert "[DRY RUN, NO FILES AFFECTED]" in result.stdout
    assert "Renamed file '123' to 'new_name.txt'" in result.stdout
    mock_get_service.assert_not_called()

@patch("pygog.commands.drive.get_service")
def test_rename_dry_run_json(mock_get_service):
    state.json_output = True
    result = runner.invoke(app, ["rename", "123", "new_name.txt", "--dry-run"])
    assert result.exit_code == 0
    assert '"dryRun": true' in result.stdout
    assert '"newName": "new_name.txt"' in result.stdout
    assert '"fileId": "123"' in result.stdout
    mock_get_service.assert_not_called()

@patch("pygog.commands.drive.get_service")
def test_move_dry_run(mock_get_service):
    result = runner.invoke(app, ["move", "123", "--parent", "folder456", "--dry-run"])
    assert result.exit_code == 0
    assert "[DRY RUN, NO FILES AFFECTED]" in result.stdout
    assert "Moved file '123' to folder folder456" in result.stdout
    mock_get_service.assert_not_called()

@patch("pygog.commands.drive.get_service")
def test_move_dry_run_json(mock_get_service):
    state.json_output = True
    result = runner.invoke(app, ["move", "123", "--parent", "folder456", "--dry-run"])
    assert result.exit_code == 0
    assert '"dryRun": true' in result.stdout
    assert '"parent": "folder456"' in result.stdout
    assert '"fileId": "123"' in result.stdout
    mock_get_service.assert_not_called()

@patch("pygog.commands.drive.get_service")
def test_delete_dry_run(mock_get_service):
    result = runner.invoke(app, ["delete", "123", "--dry-run"])
    assert result.exit_code == 0
    assert "[DRY RUN, NO FILES AFFECTED]" in result.stdout
    assert "Moved to trash: 123" in result.stdout
    mock_get_service.assert_not_called()

@patch("pygog.commands.drive.get_service")
def test_delete_dry_run_json(mock_get_service):
    state.json_output = True
    result = runner.invoke(app, ["delete", "123", "--dry-run"])
    assert result.exit_code == 0
    assert '"dryRun": true' in result.stdout
    assert '"action": "deleted"' in result.stdout
    assert '"fileId": "123"' in result.stdout
    mock_get_service.assert_not_called()
