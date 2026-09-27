"""Judge-facing API. This is the file the T2 isolation rules live in.

Three routes carry the weight:

    GET  /api/judge/scores                 the caller's own ballots
    GET  /api/judge/scores?judge=jdg_01    a named judge's ballots -- 403 unless
                                           you are that judge or an organizer
    POST /api/judge/scores                 cast or revise a ballot

The peer route is a real, working, organizer-usable endpoint rather than one
that 404s for everybody. Refusing a request you could have served is what
isolation means; concealing the route would be a different, weaker property --
and the acceptance suite agrees, since it accepts only 401 or 403 and a 404
fails the check.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, field_validator

from .. import audit, results
from ..db import query, query_one, transaction, utcnow
from ..deps import Conn, Who, default_event_id, get_event
from ..errors import ApiError
from ..security import (
    Capability,
    Identity,
    Operation,
    assert_peer_scores_allowed,
    assert_track_visible,
    deny,
    judge_record,
    judge_track_ids,
    require_capability,
    require_judge_record,
    require_operation,
)

router = APIRouter(prefix="/api/judge", tags=["judging"])


class BallotIn(BaseModel):
    """A ballot. Criteria are bounded here and again by a CHECK constraint in
    the schema, because the scale is a property of the rubric and not of the
    request."""

    model_config = {"extra": "forbid"}

    project_id: str
    criteria: dict[str, int] = Field(min_length=1)
    comment: str = Field(default="", max_length=4000)
    event_id: str | None = None

    @field_validator("criteria", mode="before")
    @classmethod
    def criteria_must_be_plain_ints(cls, value: object) -> dict[str, int]:
        if not isinstance(value, dict):
            raise ValueError("criteria must be a JSON object")
        out: dict[str, int] = {}
        for key, raw in value.items():
            if not isinstance(key, str):
                raise ValueError("criterion keys must be strings")
            # Reject bool before int(): bool is a subclass of int in Python.
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise ValueError(f"criterion '{key}' must be an integer score")
            out[key] = raw
        return out


def _scores_for_judge(
    conn: sqlite3.Connection, event_id: str, judge_id: str
) -> list[dict[str, Any]]:
    rows = query(
        conn,
        """
        SELECT s.id, s.project_id, p.title, p.track_id, s.comment, s.submitted_at, s.updated_at
          FROM scores s LEFT JOIN projects p ON p.id = s.project_id
         WHERE s.event_id = ? AND s.judge_id = ? ORDER BY s.project_id
        """,
        (event_id, judge_id),
    )
    criteria: dict[str, dict[str, int]] = {}
    for row in query(
        conn,
        """
        SELECT sc.score_id, sc.criterion_key, sc.value FROM score_criteria sc
          JOIN scores s ON s.id = sc.score_id
         WHERE s.event_id = ? AND s.judge_id = ?
        """,
        (event_id, judge_id),
    ):
        criteria.setdefault(row["score_id"], {})[row["criterion_key"]] = int(row["value"])

    weights = results.rubric_weights(conn, event_id)
    from ..normalize import weighted_value

    out = []
    for row in rows:
        ballot = criteria.get(row["id"], {})
        out.append(
            {
                "score_id": row["id"],
                "project_id": row["project_id"],
                "project_title": row["title"],
                "track_id": row["track_id"],
                "criteria": ballot,
                "weighted": round(
                    weighted_value({k: float(v) for k, v in ballot.items()}, weights), 4
                )
                if ballot
                else None,
                "comment": row["comment"],
                "submitted_at": row["submitted_at"],
                "updated_at": row["updated_at"],
            }
        )
    return out


@router.get("/scores", summary="Read judge ballots (own, or a named judge's)")
def get_scores(
    request: Request,
    conn: Conn,
    who: Who,
    judge: str | None = Query(
        default=None,
        description="Judge id. Omit for your own ballots. Naming another judge "
        "requires the peer_scores capability, which only organizers and admins hold.",
    ),
    event_id: str | None = Query(default=None),
) -> dict[str, Any]:
    event_id = event_id or default_event_id(conn)

    # An organizer holds OWN_SCORES too, but has no judge record, so the
    # capability check comes before the judge lookup.
    require_capability(conn, who, Capability.OWN_SCORES, event_id=event_id)

    own = judge_record(conn, event_id, who.user_id)
    own_judge_id = own["id"] if own else None

    if judge is None:
        if own_judge_id is None:
            # An organizer asking for "own scores" without naming a judge has
            # no ballots of their own; that is an empty list, not an error.
            return {"event_id": event_id, "judge_id": None, "scores": [], "count": 0}
        target = own_judge_id
    else:
        target = judge
        assert_peer_scores_allowed(
            conn,
            who,
            event_id=event_id,
            requested_judge_id=target,
            own_judge_id=own_judge_id,
        )
        if query_one(
            conn, "SELECT id FROM judges WHERE id = ? AND event_id = ?", (target, event_id)
        ) is None:
            raise ApiError("not_found", f"no judge '{target}' on event '{event_id}'")

    scores = _scores_for_judge(conn, event_id, target)
    if judge is not None and target != own_judge_id:
        # An organizer reading someone else's ballots is legitimate and logged.
        audit.record(
            conn,
            "judge.scores_read_as_peer",
            event_id=event_id,
            actor_user_id=who.user_id,
            actor_role=who.role,
            target_type="judge",
            target_id=target,
            detail={"count": len(scores)},
        )
    return {
        "event_id": event_id,
        "judge_id": target,
        "own": target == own_judge_id,
        "count": len(scores),
        "scores": scores,
    }


@router.get("/assignments", summary="The caller's review queue")
def get_assignments(
    conn: Conn, who: Who, event_id: str | None = Query(default=None)
) -> dict[str, Any]:
    event_id = event_id or default_event_id(conn)
    require_capability(conn, who, Capability.OWN_SCORES, event_id=event_id)
    record = require_judge_record(conn, who, event_id)

    rows = query(
        conn,
        """
        SELECT a.project_id, a.status, p.title, p.tagline, p.track_id, tr.name AS track_name,
               p.repo_url, p.live_url,
               (SELECT COUNT(*) FROM scores s
                 WHERE s.judge_id = a.judge_id AND s.project_id = a.project_id) AS scored
          FROM assignments a
          LEFT JOIN projects p ON p.id = a.project_id
          LEFT JOIN tracks tr ON tr.id = p.track_id
         WHERE a.event_id = ? AND a.judge_id = ?
         ORDER BY scored ASC, a.project_id ASC
        """,
        (event_id, record["id"]),
    )
    return {
        "event_id": event_id,
        "judge_id": record["id"],
        "tracks": sorted(judge_track_ids(conn, record["id"])),
        "pending": sum(1 for r in rows if not r["scored"]),
        "completed": sum(1 for r in rows if r["scored"]),
        "assignments": [
            {
                "project_id": r["project_id"],
                "title": r["title"],
                "tagline": r["tagline"],
                "track_id": r["track_id"],
                "track_name": r["track_name"],
                "repo_url": r["repo_url"],
                "live_url": r["live_url"],
                "scored": bool(r["scored"]),
            }
            for r in rows
        ],
    }


@router.get("/projects/{project_id}", summary="Read one assigned project")
def get_assigned_project(
    conn: Conn, who: Who, project_id: str, event_id: str | None = Query(default=None)
) -> dict[str, Any]:
    """Track isolation applies here, not only to scores.

    "A track judge must never see another track" is the half of the T2 rule the
    acceptance suite has no check for.
    """
    event_id = event_id or default_event_id(conn)
    require_capability(conn, who, Capability.OWN_SCORES, event_id=event_id)
    record = judge_record(conn, event_id, who.user_id)

    project = query_one(
        conn, "SELECT * FROM projects WHERE id = ? AND event_id = ?", (project_id, event_id)
    )
    if project is None:
        raise ApiError("not_found", f"no project '{project_id}'")

    if record is not None:
        assert_track_visible(conn, who, record["id"], project, event_id=event_id)
        assigned = query_one(
            conn,
            "SELECT 1 FROM assignments WHERE event_id = ? AND judge_id = ? AND project_id = ?",
            (event_id, record["id"], project_id),
        )
        if assigned is None:
            raise deny(
                conn,
                who,
                "not_assigned",
                detail=f"project {project_id} is not in your review queue",
                event_id=event_id,
                target_type="project",
                target_id=project_id,
            )

    own_ballot = None
    if record is not None:
        ballots = [
            b for b in _scores_for_judge(conn, event_id, record["id"])
            if b["project_id"] == project_id
        ]
        own_ballot = ballots[0] if ballots else None

    return {
        "project": {
            "id": project["id"],
            "title": project["title"],
            "tagline": project["tagline"],
            "description": project["description"],
            "repo_url": project["repo_url"],
            "live_url": project["live_url"],
            "video_url": project["video_url"],
            "track_id": project["track_id"],
        },
        "rubric": [
            dict(row)
            for row in query(
                conn,
                "SELECT key, label, description, weight, min_value, max_value "
                "FROM rubric_criteria WHERE event_id = ? ORDER BY sort, key",
                (event_id,),
            )
        ],
        "your_ballot": own_ballot,
    }


@router.post("/scores", status_code=201, summary="Cast or revise a ballot")
def post_score(request: Request, conn: Conn, who: Who, ballot: BallotIn) -> dict[str, Any]:
    event_id = ballot.event_id or default_event_id(conn)
    get_event(conn, event_id)
    require_operation(conn, who, Operation.SCORE_PROJECT, event_id=event_id)
    record = require_judge_record(conn, who, event_id)

    project = query_one(
        conn,
        "SELECT * FROM projects WHERE id = ? AND event_id = ?",
        (ballot.project_id, event_id),
    )
    if project is None:
        raise ApiError("not_found", f"no project '{ballot.project_id}' on event '{event_id}'")

    assert_track_visible(conn, who, record["id"], project, event_id=event_id)

    assigned = query_one(
        conn,
        "SELECT 1 FROM assignments WHERE event_id = ? AND judge_id = ? AND project_id = ?",
        (event_id, record["id"], ballot.project_id),
    )
    if assigned is None:
        raise deny(
            conn,
            who,
            "not_assigned",
            detail=f"project {ballot.project_id} is not in your review queue",
            event_id=event_id,
            target_type="project",
            target_id=ballot.project_id,
        )

    allowed = {
        row["key"]: row
        for row in query(
            conn,
            "SELECT key, min_value, max_value FROM rubric_criteria WHERE event_id = ?",
            (event_id,),
        )
    }
    unknown = sorted(set(ballot.criteria) - set(allowed))
    if unknown:
        raise ApiError(
            "unknown_criterion",
            f"criteria not in this event's rubric: {', '.join(unknown)}",
            extra={"unknown": unknown, "rubric": sorted(allowed)},
        )
    for key, value in ballot.criteria.items():
        bounds = allowed[key]
        if not (int(bounds["min_value"]) <= int(value) <= int(bounds["max_value"])):
            raise ApiError(
                "invalid_request",
                f"criterion '{key}' must be between {bounds['min_value']} "
                f"and {bounds['max_value']}",
            )

    score_id = f"scr_{record['id']}_{ballot.project_id}"
    now = utcnow()
    existing = query_one(conn, "SELECT id FROM scores WHERE id = ?", (score_id,))
    previous = (
        {row["criterion_key"]: row["value"] for row in query(
            conn, "SELECT criterion_key, value FROM score_criteria WHERE score_id = ?", (score_id,)
        )}
        if existing
        else None
    )

    with transaction(conn):
        conn.execute(
            """
            INSERT INTO scores (id, event_id, judge_id, project_id, comment,
                                submitted_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (event_id, judge_id, project_id) DO UPDATE SET
                comment = excluded.comment, updated_at = excluded.updated_at
            """,
            (score_id, event_id, record["id"], ballot.project_id, ballot.comment, now, now),
        )
        conn.execute("DELETE FROM score_criteria WHERE score_id = ?", (score_id,))
        for key, value in ballot.criteria.items():
            conn.execute(
                "INSERT INTO score_criteria (score_id, criterion_key, value) VALUES (?, ?, ?)",
                (score_id, key, int(value)),
            )
        conn.execute(
            "UPDATE assignments SET status = 'completed' "
            "WHERE event_id = ? AND judge_id = ? AND project_id = ?",
            (event_id, record["id"], ballot.project_id),
        )
        results.invalidate(conn, event_id)
        audit.record(
            conn,
            "score.updated" if existing else "score.created",
            event_id=event_id,
            actor_user_id=who.user_id,
            actor_role=who.role,
            target_type="project",
            target_id=ballot.project_id,
            detail={
                "judge_id": record["id"],
                "before": previous,
                "after": {k: int(v) for k, v in ballot.criteria.items()},
                "comment_length": len(ballot.comment),
            },
        )

    return {
        "score_id": score_id,
        "event_id": event_id,
        "judge_id": record["id"],
        "project_id": ballot.project_id,
        "criteria": {k: int(v) for k, v in ballot.criteria.items()},
        "revised": bool(existing),
    }
