"""All 25 cells of the published role-isolation matrix over real HTTP."""

from __future__ import annotations

import pytest

from dogfood.security import Capability, ROLE_MATRIX, has_capability

from tests.helpers import (
    FIXTURE_EVENT,
    JUDGE_A_TOKEN,
    JUDGE_B_TOKEN,
    ORG_TOKEN,
    PARTICIPANT_TOKEN,
    auth,
)

ROLE_TOKENS = {
    "visitor": None,
    "participant": PARTICIPANT_TOKEN,
    "judge": JUDGE_A_TOKEN,
    "organizer": ORG_TOKEN,
    "admin": ORG_TOKEN,
}


def _probe(client, capability: Capability, token: str | None) -> int:
    headers = auth(token)
    if capability == Capability.OWN_SCORES:
        return client.get("/api/judge/scores", headers=headers).status_code
    if capability == Capability.PEER_SCORES:
        # Must name a judge other than jdg_01 (dev judge_a); same id is own-scores path.
        return client.get("/api/judge/scores?judge=jdg_02", headers=headers).status_code
    if capability == Capability.AGGREGATE:
        return client.get(
            f"/api/organizer/results?event_id={FIXTURE_EVENT}", headers=headers
        ).status_code
    if capability == Capability.AUDIT_LOG:
        return client.get("/api/audit", headers=headers).status_code
    if capability == Capability.OTHER_TRACK:
        return client.get("/api/judge/projects/prj_01", headers=headers).status_code
    raise AssertionError(f"unknown capability {capability}")


@pytest.mark.parametrize(
    "role,capability",
    [
        (role, cap)
        for role in ROLE_MATRIX
        for cap in Capability
    ],
)
def test_role_matrix_cell(client, role: str, capability: Capability):
    allowed = has_capability(role, capability)
    status = _probe(client, capability, ROLE_TOKENS[role])
    if allowed:
        assert status == 200, f"{role} should allow {capability.value}, got {status}"
    else:
        assert status in (401, 403, 404), (
            f"{role} should deny {capability.value}, got {status}"
        )


def test_judge_b_peer_read_is_peer_scores_denied(client):
    response = client.get(
        "/api/judge/scores?judge=jdg_01",
        headers=auth(JUDGE_B_TOKEN),
    )
    assert response.status_code in (401, 403)
    assert response.json().get("code") in ("peer_scores_denied", "capability_required")
