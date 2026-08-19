from unittest.mock import patch

from typer.testing import CliRunner

from pygog.cli import state
from pygog.commands.drive import app

runner = CliRunner()


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
def test_rename_dry_run_plain_uses_tsv(mock_get_service):
    state.plain_output = True
    result = runner.invoke(app, ["rename", "123", "new_name.txt", "--dry-run"])
    assert result.exit_code == 0
    assert "dryRun\taction\tfileId\tnewName" in result.stdout
    assert "True\trename Drive file\t123\tnew_name.txt" in result.stdout
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
def test_move_dry_run_plain_uses_tsv(mock_get_service):
    state.plain_output = True
    result = runner.invoke(app, ["move", "123", "--parent", "folder456", "--dry-run"])
    assert result.exit_code == 0
    assert "dryRun\taction\tfileId\tparent" in result.stdout
    assert "True\tmove Drive file\t123\tfolder456" in result.stdout
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


@patch("pygog.commands.drive.get_service")
def test_delete_dry_run_plain_uses_tsv(mock_get_service):
    state.plain_output = True
    result = runner.invoke(app, ["delete", "123", "--dry-run"])
    assert result.exit_code == 0
    assert "dryRun\taction\tfileId" in result.stdout
    assert "True\tmove Drive file to trash\t123" in result.stdout
    mock_get_service.assert_not_called()
