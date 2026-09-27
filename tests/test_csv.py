"""RFC 4180 CSV export invariants."""

from __future__ import annotations

import csv
import io

from dogfood.exports import export_projects, to_csv

from tests.helpers import FIXTURE_EVENT


def test_csv_uses_crlf_and_no_bom(seeded_conn):
    header, rows = export_projects(seeded_conn, FIXTURE_EVENT)
    text = to_csv(header, rows)
    assert "\r\n" in text
    assert not text.startswith("\ufeff")
    assert "," in text.splitlines()[0]


def test_csv_round_trips_commas_and_quotes(seeded_conn):
    header = ["project_id", "title", "note"]
    rows = [
        ["p1", 'Say "hello", world', "line1\nline2"],
        ["p2", "normal", "ok"],
    ]
    text = to_csv(header, rows)
    reader = csv.reader(io.StringIO(text))
    parsed = list(reader)
    assert parsed[1][1] == 'Say "hello", world'
    assert parsed[1][2] == "line1\nline2"
