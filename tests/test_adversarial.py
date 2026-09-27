"""Cases fixtures.json does not cover (INTEL.md section 6)."""

from __future__ import annotations

import json

from dogfood.app import bootstrap
from dogfood.db import connect

from tests.helpers import (
    FIXTURES_PATH,
    FIXTURE_EVENT,
    JUDGE_A_TOKEN,
    ORG_TOKEN,
    PARTICIPANT_TOKEN,
    auth,
)


def test_unknown_rubric_criterion_rejected(client):
    assignments = client.get("/api/judge/assignments", headers=auth(JUDGE_A_TOKEN)).json()
    target = assignments["assignments"][0]["project_id"]
    rubric = client.get(
        f"/api/judge/projects/{target}", headers=auth(JUDGE_A_TOKEN)
    ).json()["rubric"]
    keys = {c["key"] for c in rubric}
    criteria = {k: 4 for k in keys}
    criteria["not_in_rubric"] = 4
    response = client.post(
        "/api/judge/scores",
        headers=auth(JUDGE_A_TOKEN),
        json={
            "project_id": target,
            "event_id": FIXTURE_EVENT,
            "criteria": criteria,
        },
    )
    assert 400 <= response.status_code < 500


def test_non_ascii_title_survives_gallery(client, settings):
    conn = connect(settings.db_path)
    now = "2026-01-01T12:00:00Z"
    try:
        team = conn.execute(
            "SELECT id FROM teams WHERE event_id = ? LIMIT 1", (FIXTURE_EVENT,)
        ).fetchone()
        conn.execute(
            """
            INSERT INTO projects (
                id, event_id, team_id, title, tagline, description, tech_tags,
                status, submitted_at, created_at, updated_at
            ) VALUES ('prj_unicode', ?, ?, ?, '', '', '[]', 'submitted', ?, ?, ?)
            """,
            (FIXTURE_EVENT, team["id"], "Café naïve 日本語", now, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    body = client.get("/projects").text
    assert "Café naïve 日本語" in body


def test_seed_idempotent_on_second_bootstrap(settings):
    first = bootstrap(settings.db_path, FIXTURES_PATH, dev_tokens=True)
    second = bootstrap(settings.db_path, FIXTURES_PATH, dev_tokens=True)
    assert first.get("seeded") and second.get("seeded")
    assert first["counts"]["projects"] == second["counts"]["projects"]


def test_results_embargo_for_participant(client):
    response = client.get(f"/api/events/{FIXTURE_EVENT}/vote-results", headers=auth(PARTICIPANT_TOKEN))
    assert response.status_code in (401, 403)
    assert response.json().get("code") == "results_embargoed"


def test_zero_review_project_does_not_break_results(client, settings):
    """INTEL §6: projects with no ballots must not crash ranking (nulls, not NaN)."""
    conn = connect(settings.db_path)
    now = "2026-01-01T12:00:00Z"
    try:
        team = conn.execute(
            """
            SELECT t.id AS team_id, p.track_id
              FROM teams t
              JOIN projects p ON p.team_id = t.id
             WHERE t.event_id = ?
             LIMIT 1
            """,
            (FIXTURE_EVENT,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO projects (
                id, event_id, team_id, track_id, title, tagline, description, tech_tags,
                status, submitted_at, created_at, updated_at
            ) VALUES ('prj_noreviews', ?, ?, ?, 'Lonely Pier', '', '', '[]',
                      'submitted', ?, ?, ?)
            """,
            (FIXTURE_EVENT, team["team_id"], team["track_id"], now, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    response = client.get(
        f"/api/organizer/results?event_id={FIXTURE_EVENT}",
        headers=auth(ORG_TOKEN),
    )
    assert response.status_code == 200
    board = response.json()["leaderboard"]
    row = next(r for r in board if r["project_id"] == "prj_noreviews")
    assert row["n_reviews"] == 0
    assert row["score"] is None or row.get("low_confidence")


def test_audit_chain_verifies(client):
    payload = client.get("/api/audit/verify", headers=auth(ORG_TOKEN)).json()
    assert payload["ok"] is True
    assert payload["entries"] > 0
