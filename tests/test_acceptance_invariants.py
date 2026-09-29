"""Re-assert the seven grader checks in-process so CI catches regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import (
    FIXTURE_EVENT,
    FIXTURES_PATH,
    JUDGE_A_TOKEN,
    JUDGE_B_TOKEN,
    ORG_TOKEN,
    PARTICIPANT_TOKEN,
    auth,
)


def _fixture_titles(n: int = 3) -> list[str]:
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    return [p["title"] for p in data["projects"][:n] if p.get("title")]


def test_gallery_is_public(client):
    response = client.get("/projects")
    assert response.status_code == 200


def test_fixture_titles_on_gallery_page_one(client):
    body_pages: list[str] = []
    page = 1
    while page <= 10:
        response = client.get(f"/projects?page={page}")
        assert response.status_code == 200
        body_pages.append(response.text.lower())
        if "Next" not in response.text:
            break
        page += 1
    combined = "\n".join(body_pages)
    for title in _fixture_titles():
        assert title.lower() in combined


def test_closed_event_refuses_submissions(client):
    response = client.post(
        f"/api/events/{FIXTURE_EVENT}/projects",
        headers=auth(PARTICIPANT_TOKEN),
        json={"title": "late-probe", "summary": "probe"},
    )
    assert 400 <= response.status_code < 500
    assert response.json().get("code") == "submissions_closed"


def test_judge_sees_own_scores(client):
    response = client.get("/api/judge/scores", headers=auth(JUDGE_A_TOKEN))
    assert response.status_code == 200


def test_judge_cannot_see_peer_scores(client):
    response = client.get(
        "/api/judge/scores?judge=jdg_01",
        headers=auth(JUDGE_B_TOKEN),
    )
    assert response.status_code in (401, 403)


def test_participant_blocked_from_judge_scores(client):
    response = client.get("/api/judge/scores", headers=auth(PARTICIPANT_TOKEN))
    assert response.status_code in (401, 403)


def test_csv_export_has_comma_header(client):
    response = client.get("/api/exports/results.csv", headers=auth(ORG_TOKEN))
    assert response.status_code == 200
    first = response.text.splitlines()[0]
    assert "," in first


def test_gallery_page_size_covers_fixture_count(client):
    """Every fixture title appears somewhere in the paginated gallery."""
    from dogfood.config import GALLERY_PAGE_SIZE

    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    titles = [p["title"] for p in data["projects"]]
    n = len(titles)
    assert GALLERY_PAGE_SIZE < n, "fixture set should span multiple gallery pages"
    found: set[str] = set()
    page = 1
    while page <= (n // GALLERY_PAGE_SIZE) + 2:
        body = client.get(f"/projects?page={page}").text
        for title in titles:
            if title in body:
                found.add(title)
        if "Next" not in body:
            break
        page += 1
    assert found == set(titles)
