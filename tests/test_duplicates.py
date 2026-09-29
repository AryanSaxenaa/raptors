"""Duplicate detection on fixture data (prj_41 vs prj_07)."""

from __future__ import annotations

from dogfood.seed import duplicate_report

from tests.helpers import FIXTURE_EVENT


def test_fixture_duplicate_is_flagged(seeded_conn):
    try:
        report = duplicate_report(seeded_conn, FIXTURE_EVENT)
        assert any(row["project_id"] == "prj_41" for row in report)
        row = next(r for r in report if r["project_id"] == "prj_41")
        assert row["duplicate_of"] == "prj_07"
        assert row["reviews_on_duplicate"] >= 1
    finally:
        pass


def test_duplicate_still_listed_in_gallery(client):
    """Duplicates stay in the public gallery; pagination may put them off page 1."""
    body = client.get("/projects?q=Dry+Harbour").text
    assert "Dry Harbour" in body
