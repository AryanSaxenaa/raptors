"""Integrity gates named by independent audits of this portal."""

from __future__ import annotations

from dogfood.db import connect

from tests.helpers import (
    DEMO_EVENT,
    FIXTURE_EVENT,
    ORG_TOKEN,
    PARTICIPANT_TOKEN,
    auth,
)


def test_duplicate_is_findable_via_gallery_search(client):
    body = client.get("/projects?q=Dry+Harbour").text
    assert "Dry Harbour" in body


def test_cannot_publish_results_while_voting_open(client):
    blocked = client.patch(
        f"/api/events/{FIXTURE_EVENT}",
        json={"results_published": True},
        headers=auth(ORG_TOKEN),
    )
    assert blocked.status_code == 400
    assert "voting closes" in blocked.json()["detail"].lower()


def test_votes_stop_after_results_are_published(client):
    closed = client.patch(
        f"/api/events/{FIXTURE_EVENT}",
        json={"voting_closes_at": "2020-01-01T00:00:00Z", "results_published": True},
        headers=auth(ORG_TOKEN),
    )
    assert closed.status_code == 200
    vote = client.post(
        f"/api/events/{FIXTURE_EVENT}/votes",
        json={"project_id": "prj_01", "credits": 1},
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert vote.status_code == 403
    ballot = client.get(
        f"/api/events/{FIXTURE_EVENT}/ballot",
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert ballot.status_code == 403


def test_invalid_timestamp_is_rejected_on_write(client):
    before = client.get(f"/api/events/{FIXTURE_EVENT}").json()["submissions_close"]
    bad = client.patch(
        f"/api/events/{FIXTURE_EVENT}",
        json={"submissions_close": "tomorrow-ish"},
        headers=auth(ORG_TOKEN),
    )
    assert bad.status_code == 400
    after = client.get(f"/api/events/{FIXTURE_EVENT}").json()["submissions_close"]
    assert after == before


def test_patch_cannot_move_a_project_onto_another_event_track(client):
    team = client.post(
        f"/api/events/{DEMO_EVENT}/teams",
        json={"name": "Track Isolation"},
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert team.status_code in (200, 201)
    created = client.post(
        f"/api/events/{DEMO_EVENT}/projects",
        json={"title": "Cross event track", "team": team.json()["id"], "submit": False},
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert created.status_code == 201
    patched = client.patch(
        f"/api/projects/{created.json()['id']}",
        json={"track": "trk_01"},
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert patched.status_code == 400
    assert "no track" in patched.json()["detail"]


def test_required_custom_questions_block_submit(client):
    question = client.post(
        f"/api/events/{DEMO_EVENT}/questions",
        json={"prompt": "Demo URL", "kind": "url", "required": True},
        headers=auth(ORG_TOKEN),
    )
    assert question.status_code == 201
    qid = question.json()["id"]
    team = client.post(
        f"/api/events/{DEMO_EVENT}/teams",
        json={"name": "Questions Crew"},
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert team.status_code in (200, 201)
    missing = client.post(
        f"/api/events/{DEMO_EVENT}/projects",
        json={"title": "Missing answer", "team": team.json()["id"], "submit": True},
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert missing.status_code == 400
    ok = client.post(
        f"/api/events/{DEMO_EVENT}/projects",
        json={
            "title": "Has answer",
            "team": team.json()["id"],
            "submit": True,
            "custom_answers": {qid: "https://example.com/demo"},
        },
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert ok.status_code == 201


def test_authenticated_voting_rejects_anonymous(client):
    denied = client.post(
        f"/api/events/{FIXTURE_EVENT}/votes",
        json={"project_id": "prj_01", "credits": 1},
    )
    assert denied.status_code in (401, 403)
    ballot = client.get(f"/api/events/{FIXTURE_EVENT}/ballot")
    assert ballot.status_code in (401, 403)


def test_open_and_email_voting_modes(client):
    opened = client.patch(
        f"/api/events/{FIXTURE_EVENT}",
        json={"voting_access": "open"},
        headers=auth(ORG_TOKEN),
    )
    assert opened.status_code == 200
    assert opened.json()["voting_access"] == "open"
    vote = client.post(
        f"/api/events/{FIXTURE_EVENT}/votes",
        json={"project_id": "prj_01", "credits": 1},
    )
    assert vote.status_code == 201
    assert vote.json()["voter_mode"] == "open"
    ballot = client.get(f"/api/events/{FIXTURE_EVENT}/ballot")
    assert ballot.status_code == 200

    gated = client.patch(
        f"/api/events/{FIXTURE_EVENT}",
        json={"voting_access": "email"},
        headers=auth(ORG_TOKEN),
    )
    assert gated.status_code == 200
    missing = client.post(
        f"/api/events/{FIXTURE_EVENT}/votes",
        json={"project_id": "prj_01", "credits": 2},
    )
    assert missing.status_code == 400
    emailed = client.post(
        f"/api/events/{FIXTURE_EVENT}/votes",
        json={"project_id": "prj_01", "credits": 2, "email": "voter@example.com"},
    )
    assert emailed.status_code == 201
    assert emailed.json()["voter_mode"] == "email"
    assert client.get(f"/api/events/{FIXTURE_EVENT}/ballot").status_code == 400
    assert (
        client.get(
            f"/api/events/{FIXTURE_EVENT}/ballot",
            params={"email": "voter@example.com"},
        ).status_code
        == 200
    )


def test_health_reports_schema_mismatch(client, settings):
    conn = connect(settings.db_path)
    conn.execute("UPDATE schema_meta SET value = '0' WHERE key = 'version'")
    conn.close()
    health = client.get("/api/health")
    assert health.status_code == 503
    body = health.json()
    assert body["ok"] is False
    assert body["schema_ok"] is False


def test_event_json_export_includes_configuration(client):
    snapshot = client.get(
        "/api/exports/event.json",
        params={"event_id": FIXTURE_EVENT},
        headers=auth(ORG_TOKEN),
    )
    assert snapshot.status_code == 200
    payload = snapshot.json()
    for key in (
        "prizes",
        "custom_questions",
        "assignments",
        "votes",
        "webhooks",
        "projects",
        "scores",
    ):
        assert key in payload
    assert "voting_access" in payload["event"]
    assert "images" in payload["projects"][0]
    assert "custom_answers" in payload["projects"][0]
