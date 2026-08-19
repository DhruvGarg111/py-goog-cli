from __future__ import annotations

import json
from datetime import datetime, timezone

from pygog.output.json_output import print_json, to_json


def test_to_json_preserves_wrappers_pagination_and_null_fields():
    payload = {
        "messages": [{"id": "m-1", "threadId": "t-1"}],
        "nextPageToken": "page-2",
        "resultSizeEstimate": None,
    }

    encoded = to_json(payload)

    assert json.loads(encoded) == payload


def test_to_json_serializes_datetime_without_corrupting_machine_readable_output():
    encoded = to_json({"updated": datetime(2026, 8, 19, 12, 30, tzinfo=timezone.utc)})

    assert json.loads(encoded) == {"updated": "2026-08-19 12:30:00+00:00"}


def test_print_json_is_stdout_only_and_uses_stable_indentation(capsys):
    print_json({"file": {"id": "f-1", "name": "Résumé.txt"}})

    captured = capsys.readouterr()
    assert captured.out == '{\n  "file": {\n    "id": "f-1",\n    "name": "Résumé.txt"\n  }\n}\n'
    assert captured.err == ""
