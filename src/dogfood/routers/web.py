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

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import assignment, audit, results, seed
from ..dev_session import lookup_dev_session, set_session_cookie
from ..config import GALLERY_PAGE_SIZE, TABLE_PAGE_SIZE
from ..db import parse_ts, query, query_one
from ..deps import Conn, Who, default_event_id
from ..errors import ApiError
from ..security import (
    Capability,
    Operation,
    has_capability,
    has_operation,
    judge_record,
    judge_track_ids,
)
from .community import VOTE_CREDIT_BUDGET
from .projects import gallery_rows, vote_tallies_visible

router = APIRouter(include_in_schema=False)


def _gallery_query_string(
    *,
    q: str | None = None,
    track: str | None = None,
    team: str | None = None,
    tag: str | None = None,
    sort: str | None = None,
    event: str | None = None,
    page: int | None = None,
) -> str:
    parts: dict[str, str | int] = {}
    if event:
        parts["event"] = event
    if q:
        parts["q"] = q
    if track:
        parts["track"] = track
    if team:
        parts["team"] = team
    if tag:
        parts["tag"] = tag
    if sort and sort != "arrival":
        parts["sort"] = sort
    if page and page > 1:
        parts["page"] = page
    return urlencode(parts)


def _pager_meta(*, page: int, page_size: int, total: int) -> dict[str, Any]:
    page_count = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, page_count))
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "page_count": page_count,
        "has_prev": page > 1,
        "has_next": page < page_count,
    }


def _href_with_page(
    path: str,
    query: dict[str, str | int],
    page: int,
    *,
    page_key: str = "page",
) -> str:
    parts = {k: str(v) for k, v in query.items() if v not in ("", None) and k != page_key}
    if page > 1:
        parts[page_key] = str(page)
    qs = urlencode(parts)
    return f"{path}?{qs}" if qs else path


def _pager_hrefs(
    path: str,
    query: dict[str, str | int],
    meta: dict[str, Any],
    *,
    page_key: str = "page",
) -> dict[str, str | None]:
    page = int(meta["page"])
    return {
        "prev_href": _href_with_page(path, query, page - 1, page_key=page_key)
        if meta["has_prev"]
        else None,
        "next_href": _href_with_page(path, query, page + 1, page_key=page_key)
        if meta["has_next"]
        else None,
    }


def _templates(request: Request) -> Any:
    return request.app.state.templates


def _submissions_closed(close: str | None) -> bool:
    """Same comparison the write path uses, so the page and the API agree."""
    deadline = parse_ts(close)
    if deadline is None:
        return False
    return datetime.now(timezone.utc) >= deadline


def _event_summaries(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = query(
        conn,
        "SELECT id, name, submissions_close, is_fixture FROM events "
        "ORDER BY is_fixture DESC, created_at",
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        closed = _submissions_closed(item.get("submissions_close"))
        item["submissions_closed"] = closed
        item["submissions_open"] = not closed
        out.append(item)
    return out


def _youtube_id(url: str | None) -> str | None:
    if not url:
        return None
    u = url.strip()
    if "youtu.be/" in u:
        return u.rsplit("youtu.be/", 1)[-1].split("?")[0].split("&")[0] or None
    if "youtube.com/watch" in u and "v=" in u:
        from urllib.parse import parse_qs, urlparse

        q = parse_qs(urlparse(u).query).get("v")
        return q[0] if q else None
    if "youtube.com/embed/" in u:
        return u.rsplit("embed/", 1)[-1].split("?")[0] or None
    return None


def _assigned_judge_event_id(conn: Conn, user_id: str) -> str | None:
    if not user_id:
        return None
    row = query_one(
        conn,
        "SELECT event_id FROM judges WHERE user_id = ? AND status != 'removed' "
        "ORDER BY event_id LIMIT 1",
        (user_id,),
    )
    return None if row is None else str(row["event_id"])


def _unassigned_judge_redirect(conn: Conn, who: Who, event_id: str) -> RedirectResponse | None:
    """Send people without a judges-table row away from the scoring console.

    Organizer/admin have OWN_SCORES in the published matrix so they can *read*
    ballots, but they are not a scoring judge unless assigned. The matrix is
    still enforced on the API; this redirect is only the HTML door.
    """
    if judge_record(conn, event_id, who.user_id) is not None:
        return None
    other = _assigned_judge_event_id(conn, who.user_id)
    if other and other != event_id:
        return RedirectResponse(f"/judge?event={other}", status_code=303)
    return RedirectResponse(_role_home(conn, who), status_code=303)


def _role_home(conn: Conn, who: Who) -> str:
    if who.is_anonymous:
        return "/login"
    if has_capability(who.role, Capability.AGGREGATE):
        return "/organizer"
    if _assigned_judge_event_id(conn, who.user_id):
        return "/judge"
    return "/"


def _bounce_unless(conn: Conn, who: Who, allowed: bool) -> RedirectResponse | None:
    if allowed:
        return None
    return RedirectResponse(_role_home(conn, who), status_code=303)


def _can_use_submit_workspace(who: Who) -> bool:
    """Create/join team and submit are the participant workspace.

    Organizers keep MANAGE_TEAM on the API; this HTML is the 'before you
    submit' flow, which judges and organizers should not land on.
    """
    return who.is_anonymous or has_operation(who.role, Operation.SUBMIT_PROJECT)


def _base(request: Request, conn: Conn, who: Who) -> dict[str, Any]:
    can_submit = _can_use_submit_workspace(who)
    return {
        "who": who,
        "can_aggregate": has_capability(who.role, Capability.AGGREGATE),
        "can_audit": has_capability(who.role, Capability.AUDIT_LOG),
        "is_judge": _assigned_judge_event_id(conn, who.user_id) is not None,
        "can_submit": can_submit,
        "can_manage_team": can_submit,
        "can_vote": who.is_anonymous or has_operation(who.role, Operation.VOTE),
        "events": _event_summaries(conn),
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
    sort: str = Query(default="arrival"),
    event: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
) -> Any:
    """The public gallery. Paginated so long event lists stay scannable."""
    offset = (page - 1) * GALLERY_PAGE_SIZE
    vote_event_id = event or default_event_id(conn)
    vote_row = query_one(conn, "SELECT * FROM events WHERE id = ?", (vote_event_id,))
    if vote_row is None:
        raise ApiError("not_found", f"no event '{vote_event_id}'")
    show_vote_tallies = vote_tallies_visible(conn, who, vote_event_id)
    list_sort = sort if sort in ("arrival", "newest", "title", "track", "comments", "votes") else "arrival"
    if list_sort == "votes" and not show_vote_tallies:
        list_sort = "arrival"
    items, total = gallery_rows(
        conn,
        event_id=event,
        q=q,
        track=track,
        team=team,
        tag=tag,
        sort=list_sort,
        limit=GALLERY_PAGE_SIZE,
        offset=offset,
        reveal_vote_tallies=show_vote_tallies,
    )
    tracks = query(
        conn,
        "SELECT tr.id, tr.name, COUNT(p.id) AS n FROM tracks tr "
        "LEFT JOIN projects p ON p.track_id = tr.id AND p.status IN "
        "('submitted','flagged_duplicate') GROUP BY tr.id ORDER BY tr.id",
    )
    track_rows = [dict(t) for t in tracks]
    list_qs = _gallery_query_string(
        q=q, tag=tag, sort=list_sort, event=event, team=team, track=track, page=page
    )
    pager = _pager_meta(page=page, page_size=GALLERY_PAGE_SIZE, total=total)
    gallery_q = {
        "event": event or "",
        "q": q or "",
        "track": track or "",
        "team": team or "",
        "tag": tag or "",
        "sort": list_sort if list_sort != "arrival" else "",
    }
    pager_links = _pager_hrefs("/projects", gallery_q, pager)
    filter_qs = _gallery_query_string(q=q, tag=tag, sort=list_sort, event=event, team=team)
    track_nav = [
        {
            "id": "",
            "name": "All tracks",
            "n": None,
            "href": "/projects" + (f"?{filter_qs}" if filter_qs else ""),
            "active": not track,
        }
    ]
    for t in track_rows:
        if not t["n"]:
            continue
        tqs = _gallery_query_string(
            q=q, tag=tag, sort=list_sort, event=event, team=team, track=t["id"]
        )
        track_nav.append(
            {
                "id": t["id"],
                "name": t["name"],
                "n": t["n"],
                "href": f"/projects?{tqs}",
                "active": track == t["id"],
            }
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
            "pager": {**pager, **pager_links},
            "filters": {
                "q": q or "",
                "track": track or "",
                "tag": tag or "",
                "team": team or "",
                "sort": list_sort,
                "event": event or "",
            },
            "tracks": track_rows,
            "track_nav": track_nav,
            "query_string": list_qs,
            "vote_event": dict(vote_row),
            "credit_budget": VOTE_CREDIT_BUDGET,
            "show_vote_tallies": show_vote_tallies,
        },
    )


@router.get("/projects/new", response_class=HTMLResponse)
def submit_page(request: Request, conn: Conn, who: Who, event: str | None = None) -> Any:
    """The submission form, showing the full reference field set.

    Note the page is reachable while the event is closed: it renders, and the
    API refuses the write. Hiding the form would be the frontend doing the
    enforcement, which is the thing the brief is explicit about not accepting.
    """
    bounced = _bounce_unless(conn, who, _can_use_submit_workspace(who))
    if bounced is not None:
        return bounced
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
    proj = dict(row)
    return _templates(request).TemplateResponse(
        request,
        "project.html",
        {
            **_base(request, conn, who),
            "project": proj,
            "tech_tags": json.loads(proj.get("tech_tags") or "[]"),
            "youtube_id": _youtube_id(proj.get("video_url")),
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
            "comment_count": len(comments),
            "review_count": query_one(
                conn, "SELECT COUNT(*) AS n FROM scores WHERE project_id = ?", (project_id,)
            )["n"],
            "credit_budget": VOTE_CREDIT_BUDGET,
            "images": [
                r["url"]
                for r in query(
                    conn,
                    "SELECT url FROM project_images WHERE project_id = ? ORDER BY sort",
                    (project_id,),
                )
            ],
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, conn: Conn, who: Who) -> Any:
    from ..db import transaction
    from ..seed import ensure_dev_logins

    if request.app.state.settings.dev_tokens:
        with transaction(conn):
            ensure_dev_logins(conn, dev_tokens=True)
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


@router.get("/login/as/{label}")
def login_as_seeded_session(request: Request, conn: Conn, label: str) -> RedirectResponse:
    """One-click dev sign-in without JavaScript (same sessions as quick sign-in buttons)."""
    if not request.app.state.settings.dev_tokens:
        return RedirectResponse("/login", status_code=303)
    row = lookup_dev_session(conn, label)
    if row is None:
        return RedirectResponse("/login", status_code=303)
    response = RedirectResponse("/", status_code=303)
    set_session_cookie(response, str(row["token"]))
    return response


@router.get("/judge", response_class=HTMLResponse)
def judge_console(
    request: Request,
    conn: Conn,
    who: Who,
    event: str | None = None,
    page: int = Query(default=1, ge=1),
) -> Any:
    """The review queue.

    Thirty projects in five hours is a UX problem before it is anything else, so
    the queue leads with what is unscored and every project is one click from a
    ballot.
    """
    event_id = event or default_event_id(conn)
    bounced = _unassigned_judge_redirect(conn, who, event_id)
    if bounced is not None:
        return bounced
    record = judge_record(conn, event_id, who.user_id)
    if record is None:
        return RedirectResponse("/", status_code=303)
    queue_total = query_one(
        conn,
        "SELECT COUNT(*) AS n FROM assignments WHERE event_id = ? AND judge_id = ?",
        (event_id, record["id"]),
    )["n"]
    queue_scored = query_one(
        conn,
        """
        SELECT COUNT(*) AS n FROM assignments a
         WHERE a.event_id = ? AND a.judge_id = ?
           AND EXISTS (
             SELECT 1 FROM scores s
              WHERE s.judge_id = a.judge_id AND s.project_id = a.project_id
           )
        """,
        (event_id, record["id"]),
    )["n"]
    pager = _pager_meta(page=page, page_size=TABLE_PAGE_SIZE, total=int(queue_total))
    offset = (pager["page"] - 1) * TABLE_PAGE_SIZE
    rows = query(
        conn,
        """
        SELECT a.project_id, p.title, p.tagline, p.repo_url, p.live_url, tr.name AS track_name,
               (SELECT COUNT(*) FROM scores s WHERE s.judge_id = a.judge_id
                 AND s.project_id = a.project_id) AS scored
          FROM assignments a
          LEFT JOIN projects p ON p.id = a.project_id
          LEFT JOIN tracks tr ON tr.id = p.track_id
         WHERE a.event_id = ? AND a.judge_id = ?
         ORDER BY scored ASC, a.project_id ASC
         LIMIT ? OFFSET ?
        """,
        (event_id, record["id"], TABLE_PAGE_SIZE, offset),
    )
    judge_q: dict[str, str | int] = {"event": event_id}
    pager_links = _pager_hrefs("/judge", judge_q, pager)
    return _templates(request).TemplateResponse(
        request,
        "judge.html",
        {
            **_base(request, conn, who),
            "judge": dict(record),
            "event_id": event_id,
            "tracks": sorted(judge_track_ids(conn, record["id"])),
            "queue": [dict(r) for r in rows],
            "queue_total": int(queue_total),
            "queue_scored": int(queue_scored),
            "pager": {**pager, **pager_links},
        },
    )


@router.get("/judge/projects/{project_id}", response_class=HTMLResponse)
def judge_ballot(request: Request, conn: Conn, who: Who, project_id: str) -> Any:
    from .judging import get_assigned_project

    event_id = default_event_id(conn)
    bounced = _unassigned_judge_redirect(conn, who, event_id)
    if bounced is not None:
        return bounced
    # Reuses the API handler, so the page cannot be more permissive than the
    # endpoint: the track and assignment guards are the same code.
    payload = get_assigned_project(conn, who, project_id, event_id)
    return _templates(request).TemplateResponse(
        request,
        "ballot.html",
        {**_base(request, conn, who), "event_id": event_id, **payload},
    )


@router.get("/organizer", response_class=HTMLResponse)
def organizer_dashboard(
    request: Request,
    conn: Conn,
    who: Who,
    event: str | None = None,
    page: int = Query(default=1, ge=1),
    dup_page: int = Query(default=1, ge=1),
) -> Any:
    bounced = _bounce_unless(conn, who, has_capability(who.role, Capability.AGGREGATE))
    if bounced is not None:
        return bounced
    event_id = event or default_event_id(conn)
    progress = assignment.progress(conn, event_id)
    judges = progress["judges"]
    duplicates = seed.duplicate_report(conn, event_id)
    judges_pager = _pager_meta(page=page, page_size=TABLE_PAGE_SIZE, total=len(judges))
    j_start = (judges_pager["page"] - 1) * TABLE_PAGE_SIZE
    judges_page = judges[j_start : j_start + TABLE_PAGE_SIZE]
    dup_pager = _pager_meta(page=dup_page, page_size=TABLE_PAGE_SIZE, total=len(duplicates))
    d_start = (dup_pager["page"] - 1) * TABLE_PAGE_SIZE
    duplicates_page = duplicates[d_start : d_start + TABLE_PAGE_SIZE]
    org_q: dict[str, str | int] = {}
    if event:
        org_q["event"] = event_id
    judges_q = dict(org_q)
    if dup_page > 1:
        judges_q["dup_page"] = dup_page
    dup_q = dict(org_q)
    if page > 1:
        dup_q["page"] = page
    judges_links = _pager_hrefs("/organizer", judges_q, judges_pager)
    dup_links = _pager_hrefs("/organizer", dup_q, dup_pager, page_key="dup_page")
    progress_view = {**progress, "judges": judges_page}
    return _templates(request).TemplateResponse(
        request,
        "organizer.html",
        {
            **_base(request, conn, who),
            "event": dict(query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))),
            "progress": progress_view,
            "judges_total": len(judges),
            "judges_pager": {**judges_pager, **judges_links},
            "duplicates": duplicates_page,
            "duplicates_total": len(duplicates),
            "dup_pager": {**dup_pager, **dup_links},
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
    request: Request,
    conn: Conn,
    who: Who,
    event: str | None = None,
    method: str | None = None,
    page: int = Query(default=1, ge=1),
    diag_page: int = Query(default=1, ge=1),
) -> Any:
    bounced = _bounce_unless(conn, who, has_capability(who.role, Capability.AGGREGATE))
    if bounced is not None:
        return bounced
    event_id = event or default_event_id(conn)
    result = results.get_results(conn, event_id, method=method)
    board = results.leaderboard(conn, event_id, method=method)
    pager = _pager_meta(page=page, page_size=TABLE_PAGE_SIZE, total=len(board))
    start = (pager["page"] - 1) * TABLE_PAGE_SIZE
    board_page = board[start : start + TABLE_PAGE_SIZE]
    diagnostics = result.judges
    diag_pager = _pager_meta(
        page=diag_page, page_size=TABLE_PAGE_SIZE, total=len(diagnostics)
    )
    d_start = (diag_pager["page"] - 1) * TABLE_PAGE_SIZE
    diagnostics_page = diagnostics[d_start : d_start + TABLE_PAGE_SIZE]
    results_q: dict[str, str | int] = {}
    if event:
        results_q["event"] = event_id
    if method:
        results_q["method"] = method
    if diag_page > 1:
        results_q["diag_page"] = diag_page
    leaderboard_q = dict(results_q)
    diag_q = dict(results_q)
    if page > 1:
        diag_q["page"] = page
    pager_links = _pager_hrefs("/organizer/results", leaderboard_q, pager)
    diag_links = _pager_hrefs(
        "/organizer/results", diag_q, diag_pager, page_key="diag_page"
    )
    return _templates(request).TemplateResponse(
        request,
        "results.html",
        {
            **_base(request, conn, who),
            "event_id": event_id,
            "result": result,
            "leaderboard": board_page,
            "leaderboard_total": len(board),
            "method": result.method,
            "pager": {**pager, **pager_links},
            "judge_diagnostics": diagnostics_page,
            "diag_pager": {**diag_pager, **diag_links},
        },
    )


@router.get("/organizer/audit", response_class=HTMLResponse)
def organizer_audit(
    request: Request,
    conn: Conn,
    who: Who,
    action: str | None = None,
    page: int = Query(default=1, ge=1),
) -> Any:
    """The audit trail, readable without a database client."""
    bounced = _bounce_unless(conn, who, has_capability(who.role, Capability.AUDIT_LOG))
    if bounced is not None:
        return bounced
    total = audit.count_entries(conn, action=action)
    pager = _pager_meta(page=page, page_size=TABLE_PAGE_SIZE, total=total)
    offset = (pager["page"] - 1) * TABLE_PAGE_SIZE
    audit_q: dict[str, str | int] = {}
    if action:
        audit_q["action"] = action
    pager_links = _pager_hrefs("/organizer/audit", audit_q, pager)
    return _templates(request).TemplateResponse(
        request,
        "audit.html",
        {
            **_base(request, conn, who),
            "entries": audit.list_entries(
                conn, action=action, limit=TABLE_PAGE_SIZE, offset=offset
            ),
            "chain": audit.verify_chain(conn),
            "action_filter": action or "",
            "pager": {**pager, **pager_links},
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
    bounced = _bounce_unless(conn, who, _can_use_submit_workspace(who))
    if bounced is not None:
        return bounced
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


@router.get("/vote")
def vote_page(event: str | None = None) -> RedirectResponse:
    """Voting lives on the gallery. Keep /vote as a bookmark into that page.

    The gallery route stays `/projects` (T1). Ballot shuffle stays on
    GET /api/events/{id}/ballot — this redirect must not become a second
    listing that reorders fixture titles.
    """
    qs = urlencode({"event": event}) if event else ""
    target = "/projects" + (f"?{qs}" if qs else "") + "#community-vote"
    return RedirectResponse(target, status_code=303)


@router.get("/organizer/setup", response_class=HTMLResponse)
def organizer_setup(request: Request, conn: Conn, who: Who, event: str | None = None) -> Any:
    bounced = _bounce_unless(conn, who, has_capability(who.role, Capability.AGGREGATE))
    if bounced is not None:
        return bounced
    event_id = event or default_event_id(conn)
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
def organizer_webhooks_page(
    request: Request,
    conn: Conn,
    who: Who,
    page: int = Query(default=1, ge=1),
) -> Any:
    bounced = _bounce_unless(conn, who, has_capability(who.role, Capability.AGGREGATE))
    if bounced is not None:
        return bounced
    total_row = query_one(
        conn, "SELECT COUNT(*) AS n FROM webhooks WHERE active = 1"
    )
    total = int(total_row["n"]) if total_row else 0
    pager = _pager_meta(page=page, page_size=TABLE_PAGE_SIZE, total=total)
    offset = (pager["page"] - 1) * TABLE_PAGE_SIZE
    hooks = query(
        conn,
        "SELECT id, event_id, url, active FROM webhooks WHERE active = 1 "
        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (TABLE_PAGE_SIZE, offset),
    )
    pager_links = _pager_hrefs("/organizer/webhooks", {}, pager)
    return _templates(request).TemplateResponse(
        request,
        "organizer_webhooks.html",
        {
            **_base(request, conn, who),
            "hooks": [dict(h) for h in hooks],
            "pager": {**pager, **pager_links},
        },
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


@router.get("/certificates/{project_id}", response_class=HTMLResponse)
def certificate_page(request: Request, conn: Conn, who: Who, project_id: str) -> Any:
    from .organizer import project_certificate

    cert = project_certificate(conn, who, project_id)
    return _templates(request).TemplateResponse(
        request,
        "certificate.html",
        {**_base(request, conn, who), "cert": cert},
    )
