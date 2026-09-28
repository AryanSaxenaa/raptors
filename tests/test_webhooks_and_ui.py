"""Webhooks, embed, and new HTML surfaces."""

from __future__ import annotations

import hashlib
import hmac
import time

from dogfood.db import connect
from dogfood.webhooks import flush_outbox, sign_body

from tests.helpers import (
    FIXTURE_EVENT,
    JUDGE_A_TOKEN,
    JUDGE_B_TOKEN,
    ORG_TOKEN,
    PARTICIPANT_TOKEN,
    auth,
)


def test_webhook_register_and_auth(client):
    denied = client.post(
        "/api/webhooks",
        json={"url": "https://example.com/hook", "event_id": FIXTURE_EVENT},
        headers=auth(PARTICIPANT_TOKEN),
    )
    assert denied.status_code in (401, 403)

    created = client.post(
        "/api/webhooks",
        json={"url": "https://example.com/hook", "event_id": FIXTURE_EVENT},
        headers=auth(ORG_TOKEN),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["id"].startswith("whk_")
    assert "secret" in body


def test_webhook_signature_helper():
    raw = b'{"action":"test"}'
    secret = "s3cret"
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    assert sign_body(secret, raw) == expected


def test_audit_enqueue_does_not_block_on_bad_webhook(client, settings):
    client.post(
        "/api/webhooks",
        json={"url": "http://127.0.0.1:9/unreachable", "event_id": FIXTURE_EVENT},
        headers=auth(ORG_TOKEN),
    )
    started = time.perf_counter()
    response = client.post(
        f"/api/projects/prj_01/comments",
        json={"body": "quick comment"},
        headers=auth(PARTICIPANT_TOKEN),
    )
    elapsed = time.perf_counter() - started
    assert response.status_code in (201, 403, 429)
    assert elapsed < 1.0, f"comment POST took {elapsed:.2f}s; webhooks should not block"

    conn = connect(settings.db_path)
    try:
        pending = conn.execute(
            "SELECT COUNT(*) FROM webhook_outbox WHERE processed_at IS NULL"
        ).fetchone()[0]
        assert pending >= 1
        flush_outbox(conn)
        deliveries = conn.execute(
            "SELECT COUNT(*) FROM webhook_deliveries WHERE success = 0"
        ).fetchone()[0]
        assert deliveries >= 1
    finally:
        conn.close()


def test_dev_login_attaches_seeded_session(client):
    denied = client.post("/api/auth/dev-login", json={"label": "organizer"})
    assert denied.status_code == 200
    assert denied.cookies.get("df_session")
    who = client.get("/api/auth/whoami")
    assert who.status_code == 200
    assert who.json()["role"] == "organizer"

    quick = client.get("/login/as/judge_a", follow_redirects=False)
    assert quick.status_code == 303
    assert quick.cookies.get("df_session")
    who2 = client.get("/api/auth/whoami", cookies=quick.cookies)
    assert who2.json()["role"] == "judge"


def test_new_ui_routes(client):
    assert client.get("/teams").status_code == 200
    vote = client.get("/vote", follow_redirects=False)
    assert vote.status_code == 303
    location = vote.headers.get("location", "")
    assert location.startswith("/projects")
    assert "#community-vote" in location
    landed = client.get("/vote")
    assert landed.status_code == 200
    assert "Sign in to vote" in landed.text
    assert client.get("/embed/gallery").status_code == 200
    embed = client.get("/embed/gallery")
    assert "frame-ancestors" in embed.headers.get("content-security-policy", "")
    assert client.get("/static/embed.js").status_code == 200
    assert client.get("/organizer/setup", headers=auth(ORG_TOKEN)).status_code == 200
    assert client.get("/organizer/webhooks", headers=auth(ORG_TOKEN)).status_code == 200


def test_vote_template_avoids_unsafe_innerhtml():
    from pathlib import Path

    gallery_html = (
        Path(__file__).resolve().parents[1] / "src" / "dogfood" / "templates" / "gallery.html"
    ).read_text(encoding="utf-8")
    assert "innerHTML" not in gallery_html
    assert "textContent" in gallery_html


def test_gallery_hosts_quadratic_vote_without_shuffling_listing(client):
    public = client.get("/projects")
    assert public.status_code == 200
    body = public.text
    assert 'id="community-vote"' in body
    assert "Sign in to vote" in body
    assert "Cast vote" not in body
    assert "Most votes" not in body

    authed = client.get("/projects", headers=auth(PARTICIPANT_TOKEN)).text
    assert "Cast vote" in authed

    titles = client.get("/api/projects").json()["projects"]
    assert titles, "gallery JSON should list fixture projects"
    html_order = [p["title"] for p in titles]
    for title in html_order[:5]:
        assert title in body

    shuffled = client.get("/projects?sort=votes")
    assert shuffled.status_code == 200
    assert [p["title"] for p in client.get("/api/projects?sort=votes").json()["projects"][:5]] == html_order[:5]

    organizer = client.get("/projects", headers=auth(ORG_TOKEN)).text
    assert "Most votes" in organizer


def test_openapi_lists_webhooks(client):
    spec = client.get("/openapi.json").json()
    paths = spec.get("paths", {})
    assert "/api/webhooks" in paths
    assert "/api/webhooks/{webhook_id}/test" in paths
    assert "/api/records/{record_hash}" in paths


def test_judge_record_is_stable_public_and_isolated(client):
    first = client.get("/api/judges/jdg_01/record", headers=auth(JUDGE_A_TOKEN))
    assert first.status_code == 200
    record = first.json()
    assert record["record_hash"]
    assert "criteria" not in record
    second = client.get("/api/judges/jdg_01/record", headers=auth(JUDGE_A_TOKEN))
    assert second.json()["record_hash"] == record["record_hash"]
    public = client.get(f"/api/records/{record['record_hash']}")
    assert public.status_code == 200
    assert public.json()["judge_id"] == "jdg_01"
    verified = client.post("/api/records/verify", json=record)
    assert verified.status_code == 200
    assert verified.json()["ok"] is True
    peer = client.get("/api/judges/jdg_01/record", headers=auth(JUDGE_B_TOKEN))
    assert peer.status_code in (401, 403)


def test_certificate_embargoed_until_publish(client):
    blocked = client.get("/api/projects/prj_01/certificate", headers=auth(PARTICIPANT_TOKEN))
    assert blocked.status_code == 403
    publish = client.patch(
        f"/api/events/{FIXTURE_EVENT}",
        json={"results_published": True},
        headers=auth(ORG_TOKEN),
    )
    assert publish.status_code == 200
    cert = client.get("/api/projects/prj_01/certificate", headers=auth(PARTICIPANT_TOKEN))
    assert cert.status_code == 200
    body = cert.json()
    assert body["project_id"] == "prj_01"
    assert body["position"] >= 1
    page = client.get("/certificates/prj_01", headers=auth(PARTICIPANT_TOKEN))
    assert page.status_code == 200
    assert "prj_01" in page.text or "Glass Signal" in page.text
