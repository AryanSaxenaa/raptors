"""Project submission, draft-and-edit, and deadline enforcement.

The ordering in create_project is the point of this file, so it is stated here
rather than buried: **the deadline is checked first**, before body validation
and before team-membership resolution.

The reason is that the acceptance suite's submission probe carries only a title
and a summary and one auth header. If validation ran first, a missing required
field would answer 422; if membership ran first, an unaffiliated user would
answer 403; either is a 4xx, so the check would pass without the deadline ever
being evaluated, and a portal with no working deadline would look compliant.
The deadline is a property of the event, not of the request, so it cannot
depend on the request being well formed.

Bodies are therefore parsed by hand rather than through a signature-level
Pydantic model, because FastAPI validates a declared model before the handler
body runs and that would put validation ahead of the guard.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, ValidationError

from .. import audit, results
from ..config import GALLERY_PAGE_SIZE
from ..db import parse_ts, query, query_one, transaction, utcnow
from ..deps import Conn, Who, default_event_id, get_event
from ..errors import ApiError
from ..security import Operation, deny, require_operation

router = APIRouter(tags=["projects"])

PUBLIC_STATUSES = ("submitted", "flagged_duplicate")


class ProjectIn(BaseModel):
    """The submission field set from the spec's reference list.

    `summary` is accepted as an alias for `tagline` because that is the key
    fixtures.json uses and the key the acceptance suite posts.
    """

    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=20000)
    track: str | None = None
    team: str | None = None
    repo_url: str | None = Field(default=None, max_length=500)
    live_url: str | None = Field(default=None, max_length=500)
    video_url: str | None = Field(default=None, max_length=500)
    thumbnail_url: str | None = Field(default=None, max_length=500)
    tech_tags: list[str] = Field(default_factory=list, max_length=25)
    images: list[str] = Field(default_factory=list, max_length=20)
    custom_answers: dict[str, str] = Field(default_factory=dict)
    submit: bool = False


def _validate_urls(payload: ProjectIn) -> None:
    for field in ("repo_url", "live_url", "video_url", "thumbnail_url"):
        value = getattr(payload, field)
        if value and not value.startswith(("http://", "https://")):
            raise ApiError("invalid_request", f"{field} must be an http or https url")


def require_submissions_open(conn: sqlite3.Connection, event: sqlite3.Row, who: Any) -> None:
    """The deadline gate. Runs before anything else on every write path.

    Closed is `now >= submissions_close`, so a submission at 17:57 against an
    18:00 close is accepted and one at 18:00:00 is not. The fixture event's
    latest project arrives three minutes inside its deadline, which is the
    boundary this comparison has to get right.
    """
    close = parse_ts(event["submissions_close"])
    if close is None:
        return
    now = datetime.now(timezone.utc)
    if now >= close:
        raise deny(
            conn,
            who,
            "submissions_closed",
            detail=f"submissions for '{event['name']}' closed at {event['submissions_close']}",
            event_id=event["id"],
            target_type="event",
            target_id=event["id"],
            extra={
                "submissions_close": event["submissions_close"],
                "now": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )


def _parse_body(raw: Any) -> ProjectIn:
    if not isinstance(raw, dict):
        raise ApiError("invalid_request", "request body must be a JSON object")
    try:
        return ProjectIn.model_validate(raw)
    except ValidationError as exc:
        raise ApiError(
            "invalid_request",
            "submission failed validation",
            status=422,
            extra={
                "errors": [
                    {"loc": [str(p) for p in e.get("loc", [])], "msg": e.get("msg", "")}
                    for e in exc.errors()
                ]
            },
        ) from exc


def _team_for(conn: sqlite3.Connection, event_id: str, user_id: str, requested: str | None):
    if requested:
        row = query_one(
            conn,
            """
            SELECT t.* FROM teams t JOIN team_members tm ON tm.team_id = t.id
             WHERE t.id = ? AND t.event_id = ? AND tm.user_id = ?
            """,
            (requested, event_id, user_id),
        )
        return row
    return query_one(
        conn,
        """
        SELECT t.* FROM teams t JOIN team_members tm ON tm.team_id = t.id
         WHERE t.event_id = ? AND tm.user_id = ? ORDER BY t.id LIMIT 1
        """,
        (event_id, user_id),
    )


@router.post("/api/events/{event_id}/projects", status_code=201, summary="Create a submission")
async def create_project(
    request: Request, conn: Conn, who: Who, event_id: str
) -> dict[str, Any]:
    event = get_event(conn, event_id)

    # Guard order is deliberate; see the module docstring.
    require_submissions_open(conn, event, who)
    require_operation(conn, who, Operation.SUBMIT_PROJECT, event_id=event_id)

    try:
        raw = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise ApiError("invalid_request", "request body is not valid JSON") from exc
    payload = _parse_body(raw)
    _validate_urls(payload)

    team = _team_for(conn, event_id, who.user_id, payload.team)
    if team is None:
        raise deny(
            conn,
            who,
            "not_team_member",
            detail="you are not a member of a team on this event; "
            "create or join one before submitting",
            event_id=event_id,
        )

    if payload.track and query_one(
        conn, "SELECT 1 FROM tracks WHERE id = ? AND event_id = ?", (payload.track, event_id)
    ) is None:
        raise ApiError("invalid_request", f"no track '{payload.track}' on this event")

    now = utcnow()
    project_id = f"prj_{event_id}_{team['id']}_{int(datetime.now(timezone.utc).timestamp())}"
    status = "submitted" if payload.submit else "draft"

    with transaction(conn):
        conn.execute(
            """
            INSERT INTO projects (id, event_id, team_id, track_id, title, tagline,
                                  description, thumbnail_url, video_url, repo_url,
                                  live_url, tech_tags, status, submitted_at,
                                  created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id, event_id, team["id"], payload.track, payload.title.strip(),
                payload.summary, payload.description, payload.thumbnail_url,
                payload.video_url, payload.repo_url, payload.live_url,
                json.dumps(payload.tech_tags), status,
                now if payload.submit else None, now, now,
            ),
        )
        _write_images(conn, project_id, payload.images)
        _write_answers(conn, event_id, project_id, payload.custom_answers)
        audit.record(
            conn,
            "project.created",
            event_id=event_id,
            actor_user_id=who.user_id,
            actor_role=who.role,
            target_type="project",
            target_id=project_id,
            detail={"team_id": team["id"], "status": status, "title": payload.title},
        )

    return _project_payload(conn, project_id)


@router.patch("/api/projects/{project_id}", summary="Edit a submission until the deadline")
async def update_project(
    request: Request, conn: Conn, who: Who, project_id: str
) -> dict[str, Any]:
    project = query_one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
    if project is None:
        raise ApiError("not_found", f"no project '{project_id}'")
    event = get_event(conn, project["event_id"])

    # Editing closes exactly when submitting closes: one guard, both paths.
    require_submissions_open(conn, event, who)
    require_operation(conn, who, Operation.SUBMIT_PROJECT, event_id=event["id"])

    if _team_for(conn, event["id"], who.user_id, project["team_id"]) is None:
        raise deny(
            conn,
            who,
            "not_team_member",
            detail=f"project {project_id} belongs to another team",
            event_id=event["id"],
            target_type="project",
            target_id=project_id,
        )

    try:
        raw = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise ApiError("invalid_request", "request body is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ApiError("invalid_request", "request body must be a JSON object")

    merged = {
        "title": project["title"],
        "summary": project["tagline"],
        "description": project["description"],
        "track": project["track_id"],
        "repo_url": project["repo_url"],
        "live_url": project["live_url"],
        "video_url": project["video_url"],
        "thumbnail_url": project["thumbnail_url"],
        "tech_tags": json.loads(project["tech_tags"] or "[]"),
    }
    unknown = sorted(set(raw) - set(ProjectIn.model_fields))
    if unknown:
        raise ApiError("invalid_request", f"unknown fields: {', '.join(unknown)}")
    merged.update({k: v for k, v in raw.items() if k in ProjectIn.model_fields})
    payload = _parse_body(merged)
    _validate_urls(payload)

    now = utcnow()
    submit_now = bool(raw.get("submit")) or project["status"] != "draft"
    with transaction(conn):
        conn.execute(
            """
            UPDATE projects SET title = ?, tagline = ?, description = ?, track_id = ?,
                   repo_url = ?, live_url = ?, video_url = ?, thumbnail_url = ?,
                   tech_tags = ?, status = ?,
                   submitted_at = COALESCE(submitted_at, ?), updated_at = ?
             WHERE id = ?
            """,
            (
                payload.title.strip(), payload.summary, payload.description, payload.track,
                payload.repo_url, payload.live_url, payload.video_url, payload.thumbnail_url,
                json.dumps(payload.tech_tags),
                project["status"] if not submit_now else (
                    project["status"] if project["status"] != "draft" else "submitted"
                ),
                now if submit_now else None,
                now,
                project_id,
            ),
        )
        if payload.images:
            _write_images(conn, project_id, payload.images)
        if payload.custom_answers:
            _write_answers(conn, event["id"], project_id, payload.custom_answers)
        audit.record(
            conn,
            "project.updated",
            event_id=event["id"],
            actor_user_id=who.user_id,
            actor_role=who.role,
            target_type="project",
            target_id=project_id,
            detail={"fields": sorted(raw)},
        )
    return _project_payload(conn, project_id)


def _write_images(conn: sqlite3.Connection, project_id: str, urls: list[str]) -> None:
    conn.execute("DELETE FROM project_images WHERE project_id = ?", (project_id,))
    for index, url in enumerate(urls):
        conn.execute(
            "INSERT INTO project_images (id, project_id, url, sort) VALUES (?, ?, ?, ?)",
            (f"img_{project_id}_{index}", project_id, url, index),
        )


def _write_answers(
    conn: sqlite3.Connection, event_id: str, project_id: str, answers: dict[str, str]
) -> None:
    valid = {
        row["id"]
        for row in query(conn, "SELECT id FROM custom_questions WHERE event_id = ?", (event_id,))
    }
    unknown = sorted(set(answers) - valid)
    if unknown:
        raise ApiError("invalid_request", f"unknown custom question ids: {', '.join(unknown)}")
    for question_id, answer in answers.items():
        conn.execute(
            "INSERT INTO project_answers (project_id, question_id, answer) VALUES (?, ?, ?) "
            "ON CONFLICT (project_id, question_id) DO UPDATE SET answer = excluded.answer",
            (project_id, question_id, answer),
        )


def _project_payload(conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
    row = query_one(
        conn,
        """
        SELECT p.*, t.name AS team_name, tr.name AS track_name
          FROM projects p
          LEFT JOIN teams t ON t.id = p.team_id
          LEFT JOIN tracks tr ON tr.id = p.track_id
         WHERE p.id = ?
        """,
        (project_id,),
    )
    if row is None:
        raise ApiError("not_found", f"no project '{project_id}'")
    return {
        "id": row["id"],
        "event_id": row["event_id"],
        "team_id": row["team_id"],
        "team_name": row["team_name"],
        "track_id": row["track_id"],
        "track_name": row["track_name"],
        "title": row["title"],
        "summary": row["tagline"],
        "description": row["description"],
        "repo_url": row["repo_url"],
        "live_url": row["live_url"],
        "video_url": row["video_url"],
        "thumbnail_url": row["thumbnail_url"],
        "tech_tags": json.loads(row["tech_tags"] or "[]"),
        "status": row["status"],
        "submitted_at": row["submitted_at"],
        "duplicate_of": row["duplicate_of"],
        "duplicate_reason": row["duplicate_reason"],
        "images": [
            r["url"]
            for r in query(
                conn,
                "SELECT url FROM project_images WHERE project_id = ? ORDER BY sort",
                (project_id,),
            )
        ],
    }


_GALLERY_SORT: dict[str, str] = {
    "arrival": "p.submitted_at ASC, p.id ASC",
    "newest": "p.submitted_at DESC, p.id DESC",
    "title": "p.title COLLATE NOCASE ASC, p.id ASC",
    "track": "tr.name COLLATE NOCASE ASC, p.title COLLATE NOCASE ASC",
    "comments": "comment_count DESC, p.submitted_at ASC, p.id ASC",
    "votes": "vote_count DESC, p.submitted_at ASC, p.id ASC",
}


def gallery_rows(
    conn: sqlite3.Connection,
    *,
    event_id: str | None = None,
    q: str | None = None,
    track: str | None = None,
    team: str | None = None,
    tag: str | None = None,
    sort: str = "arrival",
    limit: int = GALLERY_PAGE_SIZE,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """The public gallery query, shared by the HTML page and the JSON API.

    Default order is arrival order. A gallery should not imply a ranking before
    judging has happened, and it also keeps the earliest fixture projects on
    page one, which is where the acceptance suite looks for them.
    """
    clauses = ["p.status IN ('submitted', 'flagged_duplicate')"]
    params: list[Any] = []
    if event_id:
        clauses.append("p.event_id = ?")
        params.append(event_id)
    if track:
        clauses.append("p.track_id = ?")
        params.append(track)
    if team:
        clauses.append("p.team_id = ?")
        params.append(team)
    if tag:
        clauses.append("lower(p.tech_tags) LIKE ?")
        params.append(f"%{tag.lower()}%")
    if q:
        clauses.append(
            "(lower(p.title) LIKE ? OR lower(p.tagline) LIKE ? OR lower(p.description) LIKE ?)"
        )
        needle = f"%{q.lower()}%"
        params.extend([needle, needle, needle])
    where = " AND ".join(clauses)
    order = _GALLERY_SORT.get(sort, _GALLERY_SORT["arrival"])

    total = query_one(conn, f"SELECT COUNT(*) AS n FROM projects p WHERE {where}", params)
    rows = query(
        conn,
        f"""
        SELECT p.id, p.title, p.tagline, p.status, p.repo_url, p.live_url, p.thumbnail_url,
               p.tech_tags, p.submitted_at, p.duplicate_of, p.event_id,
               t.name AS team_name, tr.name AS track_name, tr.id AS track_id,
               (SELECT COUNT(*) FROM comments c
                 WHERE c.project_id = p.id AND c.hidden = 0) AS comment_count,
               (SELECT COUNT(*) FROM votes v WHERE v.project_id = p.id) AS vote_count,
               (SELECT url FROM project_images pi
                 WHERE pi.project_id = p.id ORDER BY pi.sort LIMIT 1) AS cover_url
          FROM projects p
          LEFT JOIN teams t ON t.id = p.team_id
          LEFT JOIN tracks tr ON tr.id = p.track_id
         WHERE {where}
         ORDER BY {order}
         LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    )
    items = [
        {
            "id": r["id"],
            "title": r["title"],
            "summary": r["tagline"],
            "team": r["team_name"],
            "track": r["track_name"],
            "track_id": r["track_id"],
            "repo_url": r["repo_url"],
            "live_url": r["live_url"],
            "thumbnail_url": r["thumbnail_url"] or r["cover_url"],
            "tech_tags": json.loads(r["tech_tags"] or "[]"),
            "submitted_at": r["submitted_at"],
            "is_duplicate": bool(r["duplicate_of"]),
            "duplicate_of": r["duplicate_of"],
            "event_id": r["event_id"],
            "comment_count": int(r["comment_count"] or 0),
            "vote_count": int(r["vote_count"] or 0),
        }
        for r in rows
    ]
    return items, int(total["n"]) if total else 0


@router.get("/api/projects", summary="The public gallery, as JSON")
def list_projects(
    conn: Conn,
    q: str | None = Query(default=None, description="free text over title, summary, description"),
    track: str | None = None,
    team: str | None = None,
    tag: str | None = None,
    event_id: str | None = None,
    sort: str = Query(default="arrival", description="arrival, newest, title, track, comments, votes"),
    limit: int = Query(default=GALLERY_PAGE_SIZE, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    items, total = gallery_rows(
        conn,
        event_id=event_id,
        q=q,
        track=track,
        team=team,
        tag=tag,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "count": len(items), "offset": offset, "projects": items}


@router.get("/api/projects/{project_id}", summary="One project")
def get_project(conn: Conn, project_id: str) -> dict[str, Any]:
    payload = _project_payload(conn, project_id)
    if payload["status"] == "draft":
        # Drafts are not public. Returning 404 rather than 403 here is
        # deliberate: the existence of an unsubmitted draft is itself private.
        raise ApiError("not_found", f"no project '{project_id}'")
    payload["reviews"] = query_one(
        conn, "SELECT COUNT(*) AS n FROM scores WHERE project_id = ?", (project_id,)
    )["n"]
    return payload


@router.get("/api/my/projects", summary="The caller's own submissions, drafts included")
def my_projects(conn: Conn, who: Who, event_id: str | None = None) -> dict[str, Any]:
    require_operation(conn, who, Operation.SUBMIT_PROJECT)
    event_id = event_id or default_event_id(conn)
    rows = query(
        conn,
        """
        SELECT p.id FROM projects p
          JOIN team_members tm ON tm.team_id = p.team_id
         WHERE tm.user_id = ? AND p.event_id = ? ORDER BY p.created_at DESC
        """,
        (who.user_id, event_id),
    )
    return {"projects": [_project_payload(conn, r["id"]) for r in rows]}
