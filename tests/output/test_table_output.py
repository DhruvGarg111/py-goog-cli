from __future__ import annotations

from io import StringIO

from rich.console import Console

from pygog.output.table_output import print_single, print_table


def _console(stream: StringIO) -> Console:
    return Console(file=stream, width=100, color_system=None, force_terminal=False)


def test_print_table_has_stable_headers_and_blank_missing_values():
    stream = StringIO()

    print_table(
        [{"id": "f-1", "name": "report.txt"}, {"id": "f-2"}],
        columns=["id", "name", "modified"],
        title="Files",
        console=_console(stream),
    )

    output = stream.getvalue()
    assert "Files" in output
    assert "ID" in output
    assert "NAME" in output
    assert "MODIFIED" in output
    assert "f-1" in output
    assert "report.txt" in output
    assert "f-2" in output


def test_print_table_empty_is_a_human_only_message():
    stream = StringIO()

    print_table([], columns=["id", "name"], console=_console(stream))

    assert stream.getvalue().strip() == "No data to display"


def test_print_single_renders_optional_null_values_as_blank():
    stream = StringIO()

    print_single({"id": "event-1", "location": None}, console=_console(stream))

    output = stream.getvalue()
    assert "event-1" in output
    assert "location" in output
    assert "None" not in output
