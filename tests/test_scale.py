"""Performance guard: large project lists stay within the grader time budget."""

from __future__ import annotations

import time

from dogfood.db import connect, transaction, utcnow

from tests.helpers import FIXTURE_EVENT


def test_four_hundred_project_gallery_stays_fast(settings, client):
    conn = connect(settings.db_path)
    now = utcnow()
    try:
        with transaction(conn):
            team = conn.execute(
                "SELECT id FROM teams WHERE event_id = ? LIMIT 1", (FIXTURE_EVENT,)
            ).fetchone()
            track = conn.execute(
                "SELECT id FROM tracks WHERE event_id = ? LIMIT 1", (FIXTURE_EVENT,)
            ).fetchone()
            assert team and track
            for index in range(360):
                pid = f"prj_scale_{index:04d}"
                conn.execute(
                    """
                    INSERT INTO projects (
                        id, event_id, team_id, track_id, title, tagline, description,
                        tech_tags, status, submitted_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, '', '', '[]', 'submitted', ?, ?, ?)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        pid,
                        FIXTURE_EVENT,
                        team["id"],
                        track["id"],
                        f"Scale Project {index}",
                        now,
                        now,
                        now,
                    ),
                )
    finally:
        conn.close()

    start = time.perf_counter()
    response = client.get("/projects")
    elapsed = time.perf_counter() - start
    assert response.status_code == 200
    assert elapsed < 8.0, f"gallery took {elapsed:.2f}s"
