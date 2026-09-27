"""Turning stored ballots into a leaderboard.

Normalization is computed here and cached in results_cache, invalidated on
score, rubric-weight and duplicate-flag changes. The acceptance suite allows a
request ten seconds before it records a hard failure, and a cold first request
that had to fit schema creation, fixture load and an iterative solve inside
that window would fail every check at once. So the solver never runs on a read
path: it runs when the data changes, and the read path is a single-row lookup.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .db import query, query_one, utcnow
from .normalize import (
    METHODS,
    NormalizationResult,
    Observation,
    ProjectResult,
    compute,
    weighted_value,
)


def rubric_weights(conn: sqlite3.Connection, event_id: str) -> dict[str, float]:
    rows = query(
        conn,
        "SELECT key, weight FROM rubric_criteria WHERE event_id = ? ORDER BY sort, key",
        (event_id,),
    )
    return {row["key"]: float(row["weight"]) for row in rows}


def event_row(conn: sqlite3.Connection, event_id: str) -> sqlite3.Row | None:
    return query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))


def observations(conn: sqlite3.Connection, event_id: str) -> list[Observation]:
    """Every ballot, collapsed to one weighted value on the rubric scale.

    Ballots on duplicate projects are included. Their project is excluded from
    the ranking, but dropping the observation would bias the bias estimate of
    whichever judge cast it.
    """
    weights = rubric_weights(conn, event_id)
    rows = query(
        conn,
        """
        SELECT s.judge_id, s.project_id, sc.criterion_key, sc.value
          FROM scores s JOIN score_criteria sc ON sc.score_id = s.id
         WHERE s.event_id = ?
        """,
        (event_id,),
    )
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        grouped.setdefault((row["judge_id"], row["project_id"]), {})[
            row["criterion_key"]
        ] = float(row["value"])
    return [
        Observation(judge_id=judge_id, project_id=project_id,
                    value=weighted_value(criteria, weights))
        for (judge_id, project_id), criteria in sorted(grouped.items())
    ]


def _excluded_project_ids(conn: sqlite3.Connection, event_id: str, exclude: bool) -> set[str]:
    if not exclude:
        return set()
    rows = query(
        conn,
        "SELECT id FROM projects WHERE event_id = ? AND duplicate_of IS NOT NULL",
        (event_id,),
    )
    return {row["id"] for row in rows}


def compute_results(
    conn: sqlite3.Connection, event_id: str, *, method: str | None = None
) -> NormalizationResult:
    event = event_row(conn, event_id)
    if event is None:
        raise KeyError(event_id)
    chosen = method or event["normalization_method"]
    if chosen not in METHODS:
        chosen = "additive_ridge"
    project_ids = [
        row["id"]
        for row in query(
            conn,
            "SELECT id FROM projects WHERE event_id = ? AND status IN "
            "('submitted', 'flagged_duplicate') ORDER BY id",
            (event_id,),
        )
    ]
    return compute(
        observations(conn, event_id),
        method=chosen,
        all_project_ids=project_ids,
        excluded_project_ids=_excluded_project_ids(
            conn, event_id, bool(event["exclude_duplicates"])
        ),
    )


def get_results(
    conn: sqlite3.Connection, event_id: str, *, method: str | None = None, refresh: bool = False
) -> NormalizationResult:
    """Cached results. `refresh=True` recomputes and rewrites the cache row."""
    event = event_row(conn, event_id)
    if event is None:
        raise KeyError(event_id)
    chosen = method or event["normalization_method"]
    if chosen not in METHODS:
        chosen = "additive_ridge"
    version = int(event["rubric_version"])

    if not refresh:
        cached = query_one(
            conn,
            "SELECT payload FROM results_cache WHERE event_id = ? AND method = ? "
            "AND rubric_version = ?",
            (event_id, chosen, version),
        )
        if cached:
            return _from_payload(json.loads(cached["payload"]))

    result = compute_results(conn, event_id, method=chosen)
    conn.execute(
        """
        INSERT INTO results_cache (event_id, method, rubric_version, computed_at, payload)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (event_id, method, rubric_version) DO UPDATE SET
            computed_at = excluded.computed_at, payload = excluded.payload
        """,
        (event_id, chosen, version, utcnow(), json.dumps(result.to_dict())),
    )
    return result


def invalidate(conn: sqlite3.Connection, event_id: str) -> None:
    """Drop cached results for an event. Called on every mutation that can
    change a score: ballots, rubric weights, duplicate flags, the method switch."""
    conn.execute("DELETE FROM results_cache WHERE event_id = ?", (event_id,))


def _from_payload(payload: dict[str, Any]) -> NormalizationResult:
    from .normalize import JudgeDiagnostic

    return NormalizationResult(
        method=payload["method"],
        projects=[ProjectResult(**p) for p in payload["projects"]],
        judges=[JudgeDiagnostic(**j) for j in payload["judges"]],
        observations=payload["observations"],
        judge_spread_before=payload["judge_spread_before"],
        judge_spread_after=payload["judge_spread_after"],
        residual_sd=payload["residual_sd"],
        iterations=payload["iterations"],
        converged=payload["converged"],
        pooled_mean=payload["pooled_mean"],
        pooled_sd=payload["pooled_sd"],
        params=payload.get("params", {}),
    )


def leaderboard(
    conn: sqlite3.Connection, event_id: str, *, method: str | None = None
) -> list[dict[str, Any]]:
    """Ranked results decorated with project and team names."""
    result = get_results(conn, event_id, method=method)
    meta = {
        row["id"]: row
        for row in query(
            conn,
            """
            SELECT p.id, p.title, p.team_id, p.track_id, p.duplicate_of,
                   t.name AS team_name, tr.name AS track_name
              FROM projects p
              LEFT JOIN teams t ON t.id = p.team_id
              LEFT JOIN tracks tr ON tr.id = p.track_id
             WHERE p.event_id = ?
            """,
            (event_id,),
        )
    }
    out = []
    for position, project in enumerate(result.ranked(), start=1):
        row = meta.get(project.project_id)
        out.append(
            {
                "position": position,
                "project_id": project.project_id,
                "title": row["title"] if row else project.project_id,
                "team": row["team_name"] if row else None,
                "track": row["track_name"] if row else None,
                "n_reviews": project.n_reviews,
                "raw": project.raw,
                "shrunken_z": project.shrunken_z,
                "additive_ridge": project.additive_ridge,
                "score": project.score(result.method),
                "std_error": project.std_error,
                "low_confidence": project.low_confidence,
                "rank_raw": project.rank_raw,
                "rank_normalized": project.rank_normalized,
                "rank_delta": project.rank_delta,
            }
        )
    return out
