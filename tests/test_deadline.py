"""Deadline enforcement: closed before validation (PLAN DECISION 08)."""

from __future__ import annotations

import pytest

from tests.helpers import FIXTURE_EVENT, PARTICIPANT_TOKEN, auth


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"title": None},
        {"title": "x" * 5000},
        {"title": "ok", "role": "organizer"},
        [],
    ],
)
def test_closed_event_returns_submissions_closed(client, body):
    response = client.post(
        f"/api/events/{FIXTURE_EVENT}/projects",
        headers=auth(PARTICIPANT_TOKEN),
        json=body,
    )
    assert 400 <= response.status_code < 500
    assert response.json().get("code") == "submissions_closed"


def test_malformed_json_on_closed_event(client):
    response = client.post(
        f"/api/events/{FIXTURE_EVENT}/projects",
        headers={**auth(PARTICIPANT_TOKEN), "Content-Type": "application/json"},
        content=b"{not json",
    )
    assert 400 <= response.status_code < 500
    payload = response.json()
    assert payload.get("code") in ("submissions_closed", "invalid_request")
