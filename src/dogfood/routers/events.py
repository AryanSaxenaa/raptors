"""Organizer configuration: events, tracks, prizes, the rubric, custom
questions, judge invitation, and team formation by invite link."""

from __future__ import annotations

import json
import re
import secrets
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field

from .. import audit, results
from ..db import query, query_one, transaction, utcnow
from ..deps import Conn, Who, get_event
from ..errors import ApiError
from ..security import Capability, Operation, require_capability, require_operation
from ..seed import DEV_PASSWORD, _upsert_user

router = APIRouter(prefix="/api", tags=["events"])


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "event"


class EventIn(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    starts_at: str | None = None
    submissions_open_at: str | None = None
    submissions_close: str | None = None
    voting_opens_at: str | None = None
    voting_closes_at: str | None = None
    reviews_per_project: int = Field(default=3, ge=1, le=20)


class EventPatch(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = None
    description: str | None = None
    submissions_close: str | None = None
    voting_opens_at: str | None = None
    voting_closes_at: str | None = None
    reviews_per_project: int | None = Field(default=None, ge=1, le=20)
    normalization_method: str | None = None
    exclude_duplicates: bool | None = None
    results_published: bool | None = None


class TrackIn(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class PrizeIn(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    amount_cents: int | None = Field(default=None, ge=0)
    currency: str = "USD"


class CriterionIn(BaseModel):
    model_config = {"extra": "forbid"}
    key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=120)
    description: str = ""
    weight: float = Field(ge=0, le=100)
    min_value: int = Field(default=1, ge=0, le=100)
    max_value: int = Field(default=5, ge=1, le=100)


class RubricIn(BaseModel):
    model_config = {"extra": "forbid"}
    criteria: list[CriterionIn] = Field(min_length=1, max_length=20)


class QuestionIn(BaseModel):
    model_config = {"extra": "forbid"}
    prompt: str = Field(min_length=1, max_length=400)
    kind: str = Field(default="text", pattern=r"^(text|longtext|url|select|boolean)$")
    options: list[str] = Field(default_factory=list, max_length=25)
    required: bool = False


class JudgeIn(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    tracks: list[str] = Field(default_factory=list, max_length=50)


class TeamIn(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=120)


class JoinIn(BaseModel):
    model_config = {"extra": "forbid"}
    invite_code: str = Field(min_length=1, max_length=120)


def _event_payload(conn: Conn, event_id: str) -> dict[str, Any]:
    row = get_event(conn, event_id)
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "description": row["description"],
        "submissions_close": row["submissions_close"],
        "voting_opens_at": row["voting_opens_at"],
        "voting_closes_at": row["voting_closes_at"],
        "results_published": bool(row["results_published"]),
        "reviews_per_project": row["reviews_per_project"],
        "normalization_method": row["normalization_method"],
        "exclude_duplicates": bool(row["exclude_duplicates"]),
        "rubric_version": row["rubric_version"],
        "is_fixture": bool(row["is_fixture"]),
        "tracks": [
            dict(r)
            for r in query(
                conn, "SELECT id, name, description FROM tracks WHERE event_id = ? ORDER BY id",
                (event_id,),
            )
        ],
        "prizes": [
            dict(r)
            for r in query(
                conn,
                "SELECT id, name, description, amount_cents, currency FROM prizes "
                "WHERE event_id = ? ORDER BY sort",
                (event_id,),
            )
        ],
        "rubric": [
            dict(r)
            for r in query(
                conn,
                "SELECT key, label, description, weight, min_value, max_value "
                "FROM rubric_criteria WHERE event_id = ? ORDER BY sort, key",
                (event_id,),
            )
        ],
        "custom_questions": [
            {**dict(r), "options": json.loads(r["options"] or "[]"),
             "required": bool(r["required"])}
            for r in query(
                conn,
                "SELECT id, prompt, kind, options, required FROM custom_questions "
                "WHERE event_id = ? ORDER BY sort",
                (event_id,),
            )
        ],
        "counts": {
            "projects": query_one(
                conn,
                "SELECT COUNT(*) AS n FROM projects WHERE event_id = ? "
                "AND status IN ('submitted','flagged_duplicate')",
                (event_id,),
            )["n"],
            "judges": query_one(
                conn, "SELECT COUNT(*) AS n FROM judges WHERE event_id = ?", (event_id,)
            )["n"],
            "scores": query_one(
                conn, "SELECT COUNT(*) AS n FROM scores WHERE event_id = ?", (event_id,)
            )["n"],
        },
    }


@router.get("/events", summary="List events")
def list_events(conn: Conn) -> dict[str, Any]:
    rows = query(conn, "SELECT id FROM events ORDER BY is_fixture DESC, created_at", ())
    return {"events": [_event_payload(conn, r["id"]) for r in rows]}


@router.get("/events/{event_id}", summary="One event with its configuration")
def read_event(conn: Conn, event_id: str) -> dict[str, Any]:
    return _event_payload(conn, event_id)


@router.post("/events", status_code=201, summary="Create an event")
def create_event(conn: Conn, who: Who, body: EventIn) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT)
    event_id = f"evt_{secrets.token_hex(4)}"
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO events (id, name, slug, description, starts_at,
                                submissions_open_at, submissions_close, voting_opens_at,
                                voting_closes_at, reviews_per_project, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id, body.name, f"{_slug(body.name)}-{event_id[-4:]}", body.description,
                body.starts_at, body.submissions_open_at, body.submissions_close,
                body.voting_opens_at, body.voting_closes_at, body.reviews_per_project, utcnow(),
            ),
        )
        # A new event with no rubric cannot be scored, so it gets the default
        # one rather than an empty table that fails silently at ballot time.
        for index, (key, label) in enumerate(
            [("functionality", "Functionality"), ("quality", "Quality"),
             ("innovation", "Innovation")]
        ):
            conn.execute(
                "INSERT INTO rubric_criteria (id, event_id, key, label, weight, sort) "
                "VALUES (?, ?, ?, ?, 1.0, ?)",
                (f"crt_{event_id}_{key}", event_id, key, label, index),
            )
        audit.record(
            conn, "event.created", event_id=event_id, actor_user_id=who.user_id,
            actor_role=who.role, target_type="event", target_id=event_id,
            detail={"name": body.name},
        )
    return _event_payload(conn, event_id)


@router.patch("/events/{event_id}", summary="Update event configuration")
def patch_event(conn: Conn, who: Who, event_id: str, body: EventPatch) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT, event_id=event_id)
    get_event(conn, event_id)
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise ApiError("invalid_request", "no fields to update")
    if "normalization_method" in fields:
        from ..normalize import METHODS

        if fields["normalization_method"] not in METHODS:
            raise ApiError(
                "invalid_request",
                f"normalization_method must be one of {', '.join(METHODS)}",
            )
    assignments = []
    params: list[Any] = []
    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        params.append(int(value) if isinstance(value, bool) else value)
    params.append(event_id)
    with transaction(conn):
        conn.execute(f"UPDATE events SET {', '.join(assignments)} WHERE id = ?", params)
        # Any of these can change a published number, so the cache goes.
        results.invalidate(conn, event_id)
        audit.record(
            conn, "event.updated", event_id=event_id, actor_user_id=who.user_id,
            actor_role=who.role, target_type="event", target_id=event_id, detail=fields,
        )
    return _event_payload(conn, event_id)


@router.post("/events/{event_id}/tracks", status_code=201, summary="Add a track")
def create_track(conn: Conn, who: Who, event_id: str, body: TrackIn) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT, event_id=event_id)
    get_event(conn, event_id)
    track_id = f"trk_{secrets.token_hex(4)}"
    with transaction(conn):
        conn.execute(
            "INSERT INTO tracks (id, event_id, name, description) VALUES (?, ?, ?, ?)",
            (track_id, event_id, body.name, body.description),
        )
        audit.record(
            conn, "track.created", event_id=event_id, actor_user_id=who.user_id,
            actor_role=who.role, target_type="track", target_id=track_id,
            detail={"name": body.name},
        )
    return {"id": track_id, "name": body.name, "description": body.description}


@router.post("/events/{event_id}/prizes", status_code=201, summary="Add a prize")
def create_prize(conn: Conn, who: Who, event_id: str, body: PrizeIn) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT, event_id=event_id)
    get_event(conn, event_id)
    prize_id = f"prz_{secrets.token_hex(4)}"
    sort = query_one(
        conn, "SELECT COALESCE(MAX(sort), -1) + 1 AS n FROM prizes WHERE event_id = ?", (event_id,)
    )["n"]
    with transaction(conn):
        conn.execute(
            "INSERT INTO prizes (id, event_id, name, description, amount_cents, currency, sort) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (prize_id, event_id, body.name, body.description, body.amount_cents,
             body.currency, sort),
        )
        audit.record(
            conn, "prize.created", event_id=event_id, actor_user_id=who.user_id,
            actor_role=who.role, target_type="prize", target_id=prize_id,
        )
    return {"id": prize_id, **body.model_dump()}


@router.put("/events/{event_id}/rubric", summary="Replace the weighted rubric")
def put_rubric(conn: Conn, who: Who, event_id: str, body: RubricIn) -> dict[str, Any]:
    """Reweighting bumps rubric_version, which is part of the results cache key,
    so every cached score is superseded rather than patched."""
    require_operation(conn, who, Operation.MANAGE_EVENT, event_id=event_id)
    get_event(conn, event_id)

    keys = [c.key for c in body.criteria]
    if len(set(keys)) != len(keys):
        raise ApiError("invalid_request", "duplicate criterion keys")
    if sum(c.weight for c in body.criteria) <= 0:
        raise ApiError("invalid_request", "at least one criterion must have a non-zero weight")
    for criterion in body.criteria:
        if criterion.max_value <= criterion.min_value:
            raise ApiError(
                "invalid_request", f"criterion '{criterion.key}': max_value must exceed min_value"
            )

    before = [
        dict(r)
        for r in query(
            conn, "SELECT key, weight FROM rubric_criteria WHERE event_id = ?", (event_id,)
        )
    ]
    with transaction(conn):
        conn.execute("DELETE FROM rubric_criteria WHERE event_id = ?", (event_id,))
        for index, criterion in enumerate(body.criteria):
            conn.execute(
                """
                INSERT INTO rubric_criteria (id, event_id, key, label, description, weight,
                                             min_value, max_value, sort)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"crt_{event_id}_{criterion.key}", event_id, criterion.key, criterion.label,
                    criterion.description, criterion.weight, criterion.min_value,
                    criterion.max_value, index,
                ),
            )
        conn.execute(
            "UPDATE events SET rubric_version = rubric_version + 1 WHERE id = ?", (event_id,)
        )
        results.invalidate(conn, event_id)
        audit.record(
            conn, "rubric.updated", event_id=event_id, actor_user_id=who.user_id,
            actor_role=who.role, target_type="event", target_id=event_id,
            detail={"before": before, "after": [c.model_dump() for c in body.criteria]},
        )
    return _event_payload(conn, event_id)


@router.post("/events/{event_id}/questions", status_code=201, summary="Add a custom question")
def create_question(conn: Conn, who: Who, event_id: str, body: QuestionIn) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT, event_id=event_id)
    get_event(conn, event_id)
    if body.kind == "select" and not body.options:
        raise ApiError("invalid_request", "a select question needs options")
    question_id = f"qst_{secrets.token_hex(4)}"
    sort = query_one(
        conn,
        "SELECT COALESCE(MAX(sort), -1) + 1 AS n FROM custom_questions WHERE event_id = ?",
        (event_id,),
    )["n"]
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO custom_questions (id, event_id, prompt, kind, options, required, sort)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (question_id, event_id, body.prompt, body.kind, json.dumps(body.options),
             int(body.required), sort),
        )
        audit.record(
            conn, "question.created", event_id=event_id, actor_user_id=who.user_id,
            actor_role=who.role, target_type="question", target_id=question_id,
        )
    return {"id": question_id, **body.model_dump()}


@router.post("/events/{event_id}/judges", status_code=201, summary="Invite a judge")
def invite_judge(conn: Conn, who: Who, event_id: str, body: JudgeIn) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_JUDGES, event_id=event_id)
    get_event(conn, event_id)
    for track_id in body.tracks:
        if query_one(
            conn, "SELECT 1 FROM tracks WHERE id = ? AND event_id = ?", (track_id, event_id)
        ) is None:
            raise ApiError("invalid_request", f"no track '{track_id}' on this event")

    judge_id = f"jdg_{secrets.token_hex(4)}"
    invite_code = f"judge-invite-{secrets.token_urlsafe(9)}"
    with transaction(conn):
        user_id = _upsert_user(
            conn, f"usr_{judge_id}", str(body.email), body.name, "judge", password=DEV_PASSWORD
        )
        existing = query_one(
            conn, "SELECT id FROM judges WHERE event_id = ? AND user_id = ?", (event_id, user_id)
        )
        if existing:
            raise ApiError("conflict", f"{body.email} is already a judge on this event")
        conn.execute(
            """
            INSERT INTO judges (id, event_id, user_id, display_name, email, status,
                                invite_code, invited_at)
            VALUES (?, ?, ?, ?, ?, 'invited', ?, ?)
            """,
            (judge_id, event_id, user_id, body.name, str(body.email), invite_code, utcnow()),
        )
        for track_id in body.tracks:
            conn.execute(
                "INSERT INTO judge_tracks (judge_id, track_id) VALUES (?, ?)",
                (judge_id, track_id),
            )
        audit.record(
            conn, "judge.invited", event_id=event_id, actor_user_id=who.user_id,
            actor_role=who.role, target_type="judge", target_id=judge_id,
            detail={"email": str(body.email), "tracks": body.tracks},
        )
    return {
        "judge_id": judge_id,
        "name": body.name,
        "email": str(body.email),
        "tracks": body.tracks,
        "invite_link": f"/judge/accept/{invite_code}",
        "status": "invited",
    }


@router.get("/events/{event_id}/judges", summary="List judges")
def list_judges(conn: Conn, who: Who, event_id: str) -> dict[str, Any]:
    # Seeing the panel and its workload is an aggregate view.
    require_capability(conn, who, Capability.AGGREGATE, event_id=event_id)
    rows = query(
        conn,
        """
        SELECT j.id, j.display_name, j.email, j.status,
               (SELECT GROUP_CONCAT(jt.track_id, ' ') FROM judge_tracks jt
                 WHERE jt.judge_id = j.id) AS tracks
          FROM judges j WHERE j.event_id = ? ORDER BY j.id
        """,
        (event_id,),
    )
    return {
        "judges": [
            {
                "judge_id": r["id"],
                "name": r["display_name"],
                "email": r["email"],
                "status": r["status"],
                "tracks": (r["tracks"] or "").split() if r["tracks"] else [],
            }
            for r in rows
        ]
    }


# ------------------------------------------------------------------- teams ---


@router.post("/events/{event_id}/teams", status_code=201, summary="Create a team")
def create_team(conn: Conn, who: Who, event_id: str, body: TeamIn) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_TEAM, event_id=event_id)
    get_event(conn, event_id)
    team_id = f"tm_{secrets.token_hex(4)}"
    invite_code = secrets.token_urlsafe(12)
    # Two different teams are allowed to pick the same display name, because
    # fixtures.json contains seven teams sharing three names between them. The
    # collision is reported rather than refused; identity is the id.
    collision = bool(
        query_one(
            conn, "SELECT 1 FROM teams WHERE event_id = ? AND name = ?", (event_id, body.name)
        )
    )
    with transaction(conn):
        conn.execute(
            "INSERT INTO teams (id, event_id, name, invite_code, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (team_id, event_id, body.name, invite_code, who.user_id, utcnow()),
        )
        conn.execute(
            "INSERT INTO team_members (team_id, user_id, role_in_team, joined_at) "
            "VALUES (?, ?, 'owner', ?)",
            (team_id, who.user_id, utcnow()),
        )
        audit.record(
            conn, "team.created", event_id=event_id, actor_user_id=who.user_id,
            actor_role=who.role, target_type="team", target_id=team_id,
            detail={"name": body.name},
        )
    return {
        "id": team_id,
        "event_id": event_id,
        "name": body.name,
        "invite_code": invite_code,
        # Team formation by invite link, as T1 specifies. The code is the
        # capability: holding it is what lets someone join.
        "invite_link": f"/teams/join/{invite_code}",
        "name_collision": collision,
    }


@router.post("/teams/join", summary="Join a team with an invite code")
def join_team(conn: Conn, who: Who, body: JoinIn) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_TEAM)
    team = query_one(conn, "SELECT * FROM teams WHERE invite_code = ?", (body.invite_code,))
    if team is None:
        raise ApiError("not_found", "no team matches that invite code")
    event = get_event(conn, team["event_id"])
    # Joining a team is part of submitting, so it closes with submissions.
    from .projects import require_submissions_open

    require_submissions_open(conn, event, who)
    with transaction(conn):
        conn.execute(
            "INSERT INTO team_members (team_id, user_id, role_in_team, joined_at) "
            "VALUES (?, ?, 'member', ?) ON CONFLICT DO NOTHING",
            (team["id"], who.user_id, utcnow()),
        )
        audit.record(
            conn, "team.joined", event_id=team["event_id"], actor_user_id=who.user_id,
            actor_role=who.role, target_type="team", target_id=team["id"],
        )
    return {"id": team["id"], "name": team["name"], "event_id": team["event_id"]}


@router.get("/teams/{team_id}", summary="One team and its members")
def read_team(conn: Conn, who: Who, team_id: str) -> dict[str, Any]:
    team = query_one(conn, "SELECT * FROM teams WHERE id = ?", (team_id,))
    if team is None:
        raise ApiError("not_found", f"no team '{team_id}'")
    members = query(
        conn,
        "SELECT u.name, u.email, tm.role_in_team FROM team_members tm "
        "JOIN users u ON u.id = tm.user_id WHERE tm.team_id = ? ORDER BY u.email",
        (team_id,),
    )
    is_member = any(
        r["email"].lower() == (who.email or "").lower() for r in members
    )
    can_see_emails = is_member or who.role in ("organizer", "admin")
    return {
        "id": team["id"],
        "name": team["name"],
        "event_id": team["event_id"],
        "members": [
            {
                "name": r["name"],
                # Member emails are personal data; visitors get names only.
                "email": r["email"] if can_see_emails else None,
                "role_in_team": r["role_in_team"],
            }
            for r in members
        ],
        "invite_code": team["invite_code"] if can_see_emails else None,
    }
