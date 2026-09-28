"""Community voting and comments (T3).

Voting is the part of this domain every incumbent concedes is gameable and
mitigates with policy -- small prizes, hidden results, a manual review -- rather
than with engineering. Four things are done here instead:

  * Quadratic credits. A voter's influence on one project is sqrt(credits), so
    concentrating a budget on a single favourite buys less and less. A loud
    minority has to spend quadratically to move a ranking.
  * Randomised ballot order, seeded per voter. Position bias is real, and an
    unseeded shuffle would reorder the ballot on every page load, which is
    hostile to the voter. The seed is the voter key, so each voter sees a
    stable order that is not the same as anyone else's.
  * Results embargoed until the organizer publishes. Enforced by capability,
    not by hiding the page.
  * Rate limits and an audit entry per ballot, so stuffing leaves a trail an
    organizer can read.

The attacks this does *not* stop are named in THREAT-MODEL.md, because an
honest list is more useful than a heroic one.
"""

from __future__ import annotations

import hashlib
import random
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from .. import audit
from ..db import parse_ts, query, query_one, transaction, utcnow
from ..deps import Conn, Who, default_event_id, get_event
from ..errors import ApiError
from ..ratelimit import check as rate_check
from ..ratelimit import client_fingerprint
from ..security import (
    Capability,
    Identity,
    Operation,
    deny,
    has_capability,
    require_operation,
)

router = APIRouter(prefix="/api", tags=["community"])

# Total credits a voter may spend across the whole event.
VOTE_CREDIT_BUDGET = 9


class CommentIn(BaseModel):
    model_config = {"extra": "forbid"}
    body: str = Field(min_length=1, max_length=2000)


class VoteIn(BaseModel):
    model_config = {"extra": "forbid"}

    project_id: str = Field(min_length=1)
    credits: int = Field(default=1, ge=1, le=VOTE_CREDIT_BUDGET)
    email: str | None = Field(default=None, max_length=320)


def _voter_key(
    request: Request, who: Identity, event: sqlite3.Row, email: str | None
) -> tuple[str, str]:
    """Identify the voter according to the event's access mode.

    Authenticated is the strongest and open-link the weakest; the mode is
    recorded on every ballot so an organizer can weigh them differently after
    the fact instead of discovering the mode was never captured.
    """
    if not who.is_anonymous:
        return f"user:{who.user_id}", "authenticated"
    if email:
        digest = hashlib.sha256(f"{event['id']}:{email.lower()}".encode()).hexdigest()[:32]
        return f"email:{digest}", "email"
    return f"open:{client_fingerprint(request)}", "open"


def _voting_open(conn: sqlite3.Connection, event: sqlite3.Row, who: Identity) -> None:
    now = datetime.now(timezone.utc)
    opens = parse_ts(event["voting_opens_at"])
    closes = parse_ts(event["voting_closes_at"])
    if opens and now < opens:
        raise deny(
            conn, who, "voting_closed",
            detail=f"voting opens at {event['voting_opens_at']}",
            event_id=event["id"],
        )
    if closes and now >= closes:
        raise deny(
            conn, who, "voting_closed",
            detail=f"voting closed at {event['voting_closes_at']}",
            event_id=event["id"],
        )


@router.get("/projects/{project_id}/comments", summary="Read comments on a project")
def list_comments(conn: Conn, project_id: str) -> dict[str, Any]:
    rows = query(
        conn,
        """
        SELECT c.id, c.body, c.created_at, u.name AS author
          FROM comments c JOIN users u ON u.id = c.user_id
         WHERE c.project_id = ? AND c.hidden = 0 ORDER BY c.created_at
        """,
        (project_id,),
    )
    return {"project_id": project_id, "comments": [dict(r) for r in rows]}


@router.post("/projects/{project_id}/comments", status_code=201, summary="Comment on a project")
def post_comment(
    request: Request, conn: Conn, who: Who, project_id: str, body: CommentIn
) -> dict[str, Any]:
    require_operation(conn, who, Operation.COMMENT)
    project = query_one(
        conn, "SELECT id, event_id, status FROM projects WHERE id = ?", (project_id,)
    )
    if project is None or project["status"] == "draft":
        raise ApiError("not_found", f"no project '{project_id}'")

    rate_check(conn, f"comment:{who.user_id}", limit=20, window_seconds=300)

    comment_id = f"cmt_{secrets.token_hex(6)}"
    with transaction(conn):
        conn.execute(
            "INSERT INTO comments (id, event_id, project_id, user_id, body, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (comment_id, project["event_id"], project_id, who.user_id, body.body, utcnow()),
        )
        audit.record(
            conn, "comment.created", event_id=project["event_id"], actor_user_id=who.user_id,
            actor_role=who.role, target_type="project", target_id=project_id,
            detail={"comment_id": comment_id, "length": len(body.body)},
        )
    return {"comment_id": comment_id, "project_id": project_id, "body": body.body}


@router.get("/events/{event_id}/ballot", summary="A voting ballot in randomised order")
def get_ballot(
    request: Request, conn: Conn, who: Who, event_id: str,
    email: str | None = Query(default=None),
) -> dict[str, Any]:
    require_operation(conn, who, Operation.VOTE)
    event = get_event(conn, event_id)
    key, mode = _voter_key(request, who, event, email)

    rows = query(
        conn,
        """
        SELECT p.id, p.title, p.tagline, tr.name AS track
          FROM projects p LEFT JOIN tracks tr ON tr.id = p.track_id
         WHERE p.event_id = ? AND p.status = 'submitted' ORDER BY p.id
        """,
        (event_id,),
    )
    items = [dict(r) for r in rows]
    # Seeded on the voter, so the order is stable for them across page loads
    # and different from every other voter's. An unseeded shuffle would move
    # the ballot under the voter's cursor on every refresh.
    random.Random(f"{event_id}:{key}").shuffle(items)

    spent = query_one(
        conn,
        "SELECT COALESCE(SUM(credits), 0) AS n FROM votes WHERE event_id = ? AND voter_key = ?",
        (event_id, key),
    )["n"]
    mine = {
        row["project_id"]: int(row["credits"])
        for row in query(
            conn,
            "SELECT project_id, credits FROM votes WHERE event_id = ? AND voter_key = ?",
            (event_id, key),
        )
    }
    for item in items:
        item["my_credits"] = mine.get(item["id"], 0)
    return {
        "event_id": event_id,
        "voter_mode": mode,
        "credit_budget": VOTE_CREDIT_BUDGET,
        "credits_spent": int(spent),
        "credits_remaining": max(VOTE_CREDIT_BUDGET - int(spent), 0),
        "influence_rule": "influence on a project is sqrt(credits spent on it)",
        "ordering": "randomised, seeded per voter to remove position bias",
        "projects": items,
    }


@router.post("/events/{event_id}/votes", status_code=201, summary="Cast a community vote")
def post_vote(
    request: Request, conn: Conn, who: Who, event_id: str, body: VoteIn
) -> dict[str, Any]:
    require_operation(conn, who, Operation.VOTE)
    event = get_event(conn, event_id)
    _voting_open(conn, event, who)

    project = query_one(
        conn,
        "SELECT id, status FROM projects WHERE id = ? AND event_id = ?",
        (body.project_id, event_id),
    )
    if project is None or project["status"] == "draft":
        raise ApiError("not_found", f"no project '{body.project_id}' on this event")

    key, mode = _voter_key(request, who, event, str(body.email) if body.email else None)

    # Two limits: a burst limit on the request, and a hard credit budget per
    # voter for the whole event.
    rate_check(conn, f"vote:{event_id}:{key}", limit=30, window_seconds=3600)
    spent = int(
        query_one(
            conn,
            "SELECT COALESCE(SUM(credits), 0) AS n FROM votes WHERE event_id = ? "
            "AND voter_key = ? AND project_id != ?",
            (event_id, key, body.project_id),
        )["n"]
    )
    if spent + body.credits > VOTE_CREDIT_BUDGET:
        raise ApiError(
            "invalid_request",
            f"credit budget exceeded: {spent} of {VOTE_CREDIT_BUDGET} already spent",
            extra={"spent": spent, "budget": VOTE_CREDIT_BUDGET},
        )

    vote_id = f"vot_{secrets.token_hex(6)}"
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO votes (id, event_id, project_id, voter_key, voter_mode, credits,
                               created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (event_id, project_id, voter_key) DO UPDATE SET
                credits = excluded.credits, created_at = excluded.created_at
            """,
            (vote_id, event_id, body.project_id, key, mode, body.credits, utcnow()),
        )
        audit.record(
            conn, "vote.cast", event_id=event_id, actor_user_id=who.user_id or None,
            actor_role=who.role, target_type="project", target_id=body.project_id,
            detail={"voter_mode": mode, "credits": body.credits, "voter_key": key},
        )
    return {
        "project_id": body.project_id,
        "credits": body.credits,
        "influence": round(body.credits**0.5, 4),
        "voter_mode": mode,
    }


@router.get("/events/{event_id}/vote-results", summary="Community vote tally")
def vote_results(conn: Conn, who: Who, event_id: str) -> dict[str, Any]:
    """Hidden until the organizer publishes. Organizers can always see it,
    which is the point of an embargo rather than a secret."""
    event = get_event(conn, event_id)
    if not event["results_published"] and not has_capability(who.role, Capability.AGGREGATE):
        raise deny(
            conn, who, "results_embargoed",
            detail="community vote results are hidden until the voting window closes",
            event_id=event_id, target_type="event", target_id=event_id,
        )

    rows = query(
        conn,
        """
        SELECT v.project_id, p.title, SUM(v.credits) AS credits, COUNT(*) AS voters,
               SUM(CASE WHEN v.voter_mode = 'open' THEN 1 ELSE 0 END) AS open_votes
          FROM votes v LEFT JOIN projects p ON p.id = v.project_id
         WHERE v.event_id = ? GROUP BY v.project_id ORDER BY credits DESC
        """,
        (event_id,),
    )
    tally = []
    for row in rows:
        # Influence is summed per voter as sqrt(their credits on this project),
        # which is where quadratic voting actually bites.
        per_voter = query(
            conn,
            "SELECT credits FROM votes WHERE event_id = ? AND project_id = ?",
            (event_id, row["project_id"]),
        )
        influence = sum(int(r["credits"]) ** 0.5 for r in per_voter)
        tally.append(
            {
                "project_id": row["project_id"],
                "title": row["title"],
                "voters": int(row["voters"]),
                "credits": int(row["credits"]),
                "influence": round(influence, 4),
                "open_link_votes": int(row["open_votes"]),
            }
        )
    tally.sort(key=lambda item: -item["influence"])
    return {
        "event_id": event_id,
        "published": bool(event["results_published"]),
        "method": "quadratic: influence = sum over voters of sqrt(credits)",
        "tally": tally,
    }
