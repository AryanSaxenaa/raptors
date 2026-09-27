"""Server-rendered pages.

Read paths are HTML rendered on the server; write paths are JSON handled by the
API routers and called from the page with fetch(). That split is deliberate and
it is load-bearing in two places.

First, the acceptance suite greps the raw bytes of the gallery response for the
titles of fixture projects. A client-rendered gallery returns an empty shell and
fails that check while looking perfect in a browser. Rendering on the server
makes the check pass by construction, and makes the gallery work in curl, in a
reader, and with JavaScript off.

Second, it means there is exactly one write surface. Every mutation the UI can
perform is an API call the same way an external client would make it, so
"every action available in the UI is available through the API" is a property of
the architecture rather than a promise in a README.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import assignment, audit, results, seed
from ..config import GALLERY_PAGE_SIZE
from ..db import parse_ts, query, query_one
from ..deps import Conn, Who, default_event_id
from ..errors import ApiError
from ..security import Capability, has_capability, judge_record, judge_track_ids
from .projects import gallery_rows

router = APIRouter(include_in_schema=False)


def _templates(request: Request) -> Any:
    return request.app.state.templates


def _submissions_closed(close: str | None) -> bool:
    """Same comparison the write path uses, so the page and the API agree."""
    deadline = parse_ts(close)
    if deadline is None:
        return False
    return datetime.now(timezone.utc) >= deadline


def _base(request: Request, conn: Conn, who: Who) -> dict[str, Any]:
    return {
        "who": who,
        "can_aggregate": has_capability(who.role, Capability.AGGREGATE),
        "can_audit": has_capability(who.role, Capability.AUDIT_LOG),
        "is_judge": has_capability(who.role, Capability.OWN_SCORES),
        "events": [
            dict(row)
            for row in query(
                conn,
                "SELECT id, name, submissions_close, is_fixture FROM events "
                "ORDER BY is_fixture DESC, created_at",
            )
        ],
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request, conn: Conn, who: Who) -> Any:
    event_id = default_event_id(conn)
    counts = {
        "projects": query_one(
            conn,
            "SELECT COUNT(*) AS n FROM projects WHERE event_id = ? AND status IN "
            "('submitted','flagged_duplicate')",
            (event_id,),
        )["n"],
        "judges": query_one(
            conn, "SELECT COUNT(*) AS n FROM judges WHERE event_id = ?", (event_id,)
        )["n"],
        "scores": query_one(
            conn, "SELECT COUNT(*) AS n FROM scores WHERE event_id = ?", (event_id,)
        )["n"],
        "tracks": query_one(
            conn, "SELECT COUNT(*) AS n FROM tracks WHERE event_id = ?", (event_id,)
        )["n"],
    }
    return _templates(request).TemplateResponse(
        request,
        "home.html",
        {
            **_base(request, conn, who),
            "event": dict(query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))),
            "counts": counts,
            "duplicates": seed.duplicate_report(conn, event_id),
        },
    )


@router.get("/projects", response_class=HTMLResponse)
def gallery(
    request: Request,
    conn: Conn,
    who: Who,
    q: str | None = Query(default=None),
    track: str | None = Query(default=None),
    team: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    event: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
) -> Any:
    """The public gallery. No authentication, and no pagination at fixture scale.

    Page size is 200 against 41 fixture projects, and the default order is
    arrival order, so page one is the whole event and the earliest projects are
    on it. Both choices are asserted in tests/test_acceptance_invariants.py.
    """
    offset = (page - 1) * GALLERY_PAGE_SIZE
    items, total = gallery_rows(
        conn, event_id=event, q=q, track=track, team=team, tag=tag,
        limit=GALLERY_PAGE_SIZE, offset=offset,
    )
    tracks = query(
        conn,
        "SELECT tr.id, tr.name, COUNT(p.id) AS n FROM tracks tr "
        "LEFT JOIN projects p ON p.track_id = tr.id AND p.status IN "
        "('submitted','flagged_duplicate') GROUP BY tr.id ORDER BY tr.id",
    )
    return _templates(request).TemplateResponse(
        request,
        "gallery.html",
        {
            **_base(request, conn, who),
            "projects": items,
            "total": total,
            "page": page,
            "page_size": GALLERY_PAGE_SIZE,
            "filters": {"q": q or "", "track": track or "", "tag": tag or "", "team": team or ""},
            "tracks": [dict(t) for t in tracks],
        },
    )


@router.get("/projects/new", response_class=HTMLResponse)
def submit_page(request: Request, conn: Conn, who: Who, event: str | None = None) -> Any:
    """The submission form, showing the full reference field set.

    Note the page is reachable while the event is closed: it renders, and the
    API refuses the write. Hiding the form would be the frontend doing the
    enforcement, which is the thing the brief is explicit about not accepting.
    """
    event_id = event or default_event_id(conn)
    row = query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))
    if row is None:
        raise ApiError("not_found", f"no event '{event_id}'")
    teams = (
        query(
            conn,
            "SELECT t.id, t.name FROM teams t JOIN team_members tm ON tm.team_id = t.id "
            "WHERE t.event_id = ? AND tm.user_id = ? ORDER BY t.name",
            (event_id, who.user_id),
        )
        if who.user_id
        else []
    )
    return _templates(request).TemplateResponse(
        request,
        "submit.html",
        {
            **_base(request, conn, who),
            "event": dict(row),
            # The page tells you the event is closed; the API is what refuses
            # the write. Both, because a form that silently 403s is hostile and
            # a form that only disables itself is not enforcement.
            "closed": _submissions_closed(row["submissions_close"]),
            "teams": [dict(t) for t in teams],
            "tracks": [
                dict(t)
                for t in query(
                    conn, "SELECT id, name FROM tracks WHERE event_id = ? ORDER BY id", (event_id,)
                )
            ],
            "questions": [
                dict(qn)
                for qn in query(
                    conn,
                    "SELECT id, prompt, kind, required FROM custom_questions "
                    "WHERE event_id = ? ORDER BY sort",
                    (event_id,),
                )
            ],
        },
    )


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_page(request: Request, conn: Conn, who: Who, project_id: str) -> Any:
    row = query_one(
        conn,
        """
        SELECT p.*, t.name AS team_name, tr.name AS track_name, e.name AS event_name
          FROM projects p
          LEFT JOIN teams t ON t.id = p.team_id
          LEFT JOIN tracks tr ON tr.id = p.track_id
          LEFT JOIN events e ON e.id = p.event_id
         WHERE p.id = ?
        """,
        (project_id,),
    )
    if row is None or row["status"] == "draft":
        raise ApiError("not_found", f"no project '{project_id}'")
    comments = query(
        conn,
        "SELECT c.body, c.created_at, u.name AS author FROM comments c "
        "JOIN users u ON u.id = c.user_id WHERE c.project_id = ? AND c.hidden = 0 "
        "ORDER BY c.created_at",
        (project_id,),
    )
    return _templates(request).TemplateResponse(
        request,
        "project.html",
        {
            **_base(request, conn, who),
            "project": dict(row),
            "members": [
                dict(m)
                for m in query(
                    conn,
                    "SELECT u.name FROM team_members tm JOIN users u ON u.id = tm.user_id "
                    "WHERE tm.team_id = ? ORDER BY u.name",
                    (row["team_id"],),
                )
            ],
            "comments": [dict(c) for c in comments],
            "review_count": query_one(
                conn, "SELECT COUNT(*) AS n FROM scores WHERE project_id = ?", (project_id,)
            )["n"],
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, conn: Conn, who: Who) -> Any:
    logins = query(
        conn,
        """
        SELECT s.label, s.token, u.email, u.role, u.name FROM sessions s
          JOIN users u ON u.id = s.user_id
         WHERE s.label IN ('organizer','judge_a','judge_b','participant','admin')
         ORDER BY CASE s.label WHEN 'organizer' THEN 1 WHEN 'judge_a' THEN 2
                               WHEN 'judge_b' THEN 3 WHEN 'participant' THEN 4 ELSE 5 END
        """,
    )
    return _templates(request).TemplateResponse(
        request,
        "login.html",
        {**_base(request, conn, who), "seeded_logins": [dict(r) for r in logins]},
    )


@router.get("/judge", response_class=HTMLResponse)
def judge_console(request: Request, conn: Conn, who: Who, event: str | None = None) -> Any:
    """The review queue.

    Thirty projects in five hours is a UX problem before it is anything else, so
    the queue leads with what is unscored and every project is one click from a
    ballot.
    """
    event_id = event or default_event_id(conn)
    if not has_capability(who.role, Capability.OWN_SCORES):
        return RedirectResponse("/login", status_code=303)
    record = judge_record(conn, event_id, who.user_id)
    if record is None:
        return _templates(request).TemplateResponse(
            request,
            "judge.html",
            {**_base(request, conn, who), "judge": None, "event_id": event_id, "queue": []},
        )
    rows = query(
        conn,
        """
        SELECT a.project_id, p.title, p.tagline, p.repo_url, p.live_url, tr.name AS track_name,
               (SELECT COUNT(*) FROM scores s WHERE s.judge_id = a.judge_id
                 AND s.project_id = a.project_id) AS scored
          FROM assignments a
          LEFT JOIN projects p ON p.id = a.project_id
          LEFT JOIN tracks tr ON tr.id = p.track_id
         WHERE a.event_id = ? AND a.judge_id = ? ORDER BY scored ASC, a.project_id ASC
        """,
        (event_id, record["id"]),
    )
    return _templates(request).TemplateResponse(
        request,
        "judge.html",
        {
            **_base(request, conn, who),
            "judge": dict(record),
            "event_id": event_id,
            "tracks": sorted(judge_track_ids(conn, record["id"])),
            "queue": [dict(r) for r in rows],
        },
    )


@router.get("/judge/projects/{project_id}", response_class=HTMLResponse)
def judge_ballot(request: Request, conn: Conn, who: Who, project_id: str) -> Any:
    from .judging import get_assigned_project

    event_id = default_event_id(conn)
    if not has_capability(who.role, Capability.OWN_SCORES):
        return RedirectResponse("/login", status_code=303)
    # Reuses the API handler, so the page cannot be more permissive than the
    # endpoint: the track and assignment guards are the same code.
    payload = get_assigned_project(conn, who, project_id, event_id)
    return _templates(request).TemplateResponse(
        request,
        "ballot.html",
        {**_base(request, conn, who), "event_id": event_id, **payload},
    )


@router.get("/organizer", response_class=HTMLResponse)
def organizer_dashboard(request: Request, conn: Conn, who: Who, event: str | None = None) -> Any:
    event_id = event or default_event_id(conn)
    if not has_capability(who.role, Capability.AGGREGATE):
        return RedirectResponse("/login", status_code=303)
    return _templates(request).TemplateResponse(
        request,
        "organizer.html",
        {
            **_base(request, conn, who),
            "event": dict(query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))),
            "progress": assignment.progress(conn, event_id),
            "duplicates": seed.duplicate_report(conn, event_id),
            "rubric": [
                dict(r)
                for r in query(
                    conn,
                    "SELECT key, label, weight FROM rubric_criteria WHERE event_id = ? "
                    "ORDER BY sort",
                    (event_id,),
                )
            ],
        },
    )


@router.get("/organizer/results", response_class=HTMLResponse)
def organizer_results(
    request: Request, conn: Conn, who: Who, event: str | None = None, method: str | None = None
) -> Any:
    event_id = event or default_event_id(conn)
    if not has_capability(who.role, Capability.AGGREGATE):
        return RedirectResponse("/login", status_code=303)
    result = results.get_results(conn, event_id, method=method)
    return _templates(request).TemplateResponse(
        request,
        "results.html",
        {
            **_base(request, conn, who),
            "event_id": event_id,
            "result": result,
            "leaderboard": results.leaderboard(conn, event_id, method=method),
            "method": result.method,
        },
    )


@router.get("/organizer/audit", response_class=HTMLResponse)
def organizer_audit(
    request: Request, conn: Conn, who: Who, action: str | None = None, limit: int = 150
) -> Any:
    """The audit trail, readable without a database client."""
    if not has_capability(who.role, Capability.AUDIT_LOG):
        return RedirectResponse("/login", status_code=303)
    return _templates(request).TemplateResponse(
        request,
        "audit.html",
        {
            **_base(request, conn, who),
            "entries": audit.list_entries(conn, action=action, limit=limit),
            "chain": audit.verify_chain(conn),
            "action_filter": action or "",
            "actions": [
                r["action"]
                for r in query(
                    conn, "SELECT DISTINCT action FROM audit_log ORDER BY action"
                )
            ],
        },
    )


@router.get("/teams", response_class=HTMLResponse)
def teams_page(
    request: Request,
    conn: Conn,
    who: Who,
    event: str | None = None,
    invite: str | None = Query(default=None),
) -> Any:
    event_id = event or default_event_id(conn)
    row = query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))
    if row is None:
        raise ApiError("not_found", f"no event '{event_id}'")
    my_teams = (
        query(
            conn,
            "SELECT t.id, t.name FROM teams t JOIN team_members tm ON tm.team_id = t.id "
            "WHERE t.event_id = ? AND tm.user_id = ? ORDER BY t.name",
            (event_id, who.user_id),
        )
        if who.user_id
        else []
    )
    return _templates(request).TemplateResponse(
        request,
        "teams.html",
        {
            **_base(request, conn, who),
            "event": dict(row),
            "my_teams": [dict(t) for t in my_teams],
            "invite_prefill": invite or "",
        },
    )


@router.get("/teams/join/{invite_code}", response_class=HTMLResponse)
def teams_join_link(
    request: Request, conn: Conn, who: Who, invite_code: str, event: str | None = None
) -> Any:
    team = query_one(conn, "SELECT event_id FROM teams WHERE invite_code = ?", (invite_code,))
    event_id = event or (team["event_id"] if team else default_event_id(conn))
    return teams_page(request, conn, who, event=event_id, invite=invite_code)


@router.get("/vote", response_class=HTMLResponse)
def vote_page(request: Request, conn: Conn, who: Who, event: str | None = None) -> Any:
    event_id = event or default_event_id(conn)
    row = query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))
    if row is None:
        raise ApiError("not_found", f"no event '{event_id}'")
    from ..routers.community import VOTE_CREDIT_BUDGET

    return _templates(request).TemplateResponse(
        request,
        "vote.html",
        {
            **_base(request, conn, who),
            "event": dict(row),
            "credit_budget": VOTE_CREDIT_BUDGET,
        },
    )


@router.get("/organizer/setup", response_class=HTMLResponse)
def organizer_setup(request: Request, conn: Conn, who: Who, event: str | None = None) -> Any:
    event_id = event or default_event_id(conn)
    if not has_capability(who.role, Capability.AGGREGATE):
        return RedirectResponse("/login", status_code=303)
    row = query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))
    if row is None:
        raise ApiError("not_found", f"no event '{event_id}'")
    tracks = query(
        conn, "SELECT id, name FROM tracks WHERE event_id = ? ORDER BY id", (event_id,)
    )
    return _templates(request).TemplateResponse(
        request,
        "organizer_setup.html",
        {
            **_base(request, conn, who),
            "event": dict(row),
            "tracks": [dict(t) for t in tracks],
        },
    )


@router.get("/organizer/webhooks", response_class=HTMLResponse)
def organizer_webhooks_page(request: Request, conn: Conn, who: Who) -> Any:
    if not has_capability(who.role, Capability.AGGREGATE):
        return RedirectResponse("/login", status_code=303)
    hooks = query(
        conn,
        "SELECT id, event_id, url, active FROM webhooks WHERE active = 1 ORDER BY created_at DESC",
    )
    return _templates(request).TemplateResponse(
        request,
        "organizer_webhooks.html",
        {**_base(request, conn, who), "hooks": [dict(h) for h in hooks]},
    )


@router.get("/embed/gallery", response_class=HTMLResponse)
def embed_gallery(
    request: Request,
    conn: Conn,
    event: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> Any:
    event_id = event or default_event_id(conn)
    row = query_one(conn, "SELECT id, name FROM events WHERE id = ?", (event_id,))
    if row is None:
        raise ApiError("not_found", f"no event '{event_id}'")
    items, total = gallery_rows(conn, event_id=event_id, limit=limit, offset=0)
    config = request.app.state.settings
    response = _templates(request).TemplateResponse(
        request,
        "embed_gallery.html",
        {
            "event": dict(row),
            "projects": items,
            "total": total,
            "portal_url": config.base_url.rstrip("/"),
        },
    )
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response
