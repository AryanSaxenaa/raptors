"""Constants and helpers shared by pytest modules (not fixtures)."""

from __future__ import annotations

from dogfood.config import REPO_ROOT

FIXTURES_PATH = REPO_ROOT / "fixtures.json"

ORG_TOKEN = "org_7f2a"
JUDGE_A_TOKEN = "jdg_a_91bc"
JUDGE_B_TOKEN = "jdg_b_44de"
PARTICIPANT_TOKEN = "prt_2e88"

FIXTURE_EVENT = "evt_01"
DEMO_EVENT = "evt_demo"


def auth(token: str | None) -> dict[str, str]:
    if not token:
        return {}
    return {"Cookie": f"df_session={token}"}
