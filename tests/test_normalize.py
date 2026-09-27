"""Normalization invariants on the published fixture data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dogfood.normalize import K_SHRINK, Observation, compute, weighted_value

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures.json"


@pytest.fixture(scope="module")
def fixtures() -> dict:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def _observations(fixtures: dict) -> list[Observation]:
    weights = {k: 1.0 for k in fixtures["scores"][0]["criteria"]}
    out: list[Observation] = []
    for row in fixtures["scores"]:
        crit = row["criteria"]
        value = weighted_value(crit, weights)
        out.append(
            Observation(
                judge_id=row["judge"],
                project_id=row["project"],
                value=value,
            )
        )
    return out


def test_fixture_spread_drops_after_calibration(fixtures: dict):
    result = compute(_observations(fixtures), method="additive_ridge", excluded_project_ids={"prj_41"})
    assert result.converged
    assert result.judge_spread_after < result.judge_spread_before
    assert result.judge_spread_before > 0.3


def test_zero_variance_judge_is_flagged_not_nan(fixtures: dict):
    result = compute(_observations(fixtures), method="additive_ridge", excluded_project_ids={"prj_41"})
    flat = next(j for j in result.judges if j.judge_id == "jdg_07")
    assert flat.is_flat
    assert flat.raw_sd == 0
    assert flat.shrunk_sd > 0


def test_duplicate_excluded_from_ranking(fixtures: dict):
    result = compute(_observations(fixtures), method="additive_ridge", excluded_project_ids={"prj_41"})
    ranked = result.ranked()
    assert len(ranked) == 40
    assert all(p.project_id != "prj_41" for p in ranked)


def test_k_shrink_constant():
    assert K_SHRINK == 5.0
