from typer.testing import CliRunner

from pygog.commands import gmail


def test_thread_get_does_not_advertise_unimplemented_attachment_options():
    result = CliRunner().invoke(gmail.app, ["thread", "get", "--help"])

    assert result.exit_code == 0, result.output
    assert "--download" not in result.output
    assert "--out-dir" not in result.output
