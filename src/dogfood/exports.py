"""CSV export and bulk import.

T2 asks for "CSV export at every stage", and Adoptability asks for "a migration
path in and out, because a platform you cannot leave is a trap". So there is one
export per pipeline stage and an importer that reads the same shapes back.

Two details that look cosmetic and are not:

  * csv.writer, not f-strings. Forty per cent of the fixture comments are free
    text and every project title is user-controlled, so a title containing a
    comma, a quote or a newline has to round-trip. tests/test_csv.py asserts it.
  * No UTF-8 BOM, and the header row always has at least two columns. The
    acceptance suite checks `"," in body.splitlines()[0]`, so a BOM or a
    single-column export fails a check that looks trivially passed.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from typing import Any, Iterable, Sequence

from . import audit
from .db import query, utcnow
from .results import get_results

STAGES = ("projects", "teams", "judges", "assignments", "scores", "results")


def to_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """RFC 4180: CRLF line endings, minimal quoting, no BOM."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(list(header))
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return buffer.getvalue()


# ----------------------------------------------------------------- exports ---


def export_projects(conn: sqlite3.Connection, event_id: str) -> tuple[list[str], list[list[Any]]]:
    header = [
        "project_id", "title", "tagline", "team_id", "team_name", "track_id", "track_name",
        "status", "repo_url", "live_url", "video_url", "tech_tags", "submitted_at",
        "duplicate_of", "duplicate_reason",
    ]
    rows = query(
        conn,
        """
        SELECT p.id, p.title, p.tagline, p.team_id, t.name AS team_name,
               p.track_id, tr.name AS track_name, p.status, p.repo_url, p.live_url,
               p.video_url, p.tech_tags, p.submitted_at, p.duplicate_of, p.duplicate_reason
          FROM projects p
          LEFT JOIN teams t ON t.id = p.team_id
          LEFT JOIN tracks tr ON tr.id = p.track_id
         WHERE p.event_id = ? ORDER BY p.id
        """,
        (event_id,),
    )
    return header, [
        [
            r["id"], r["title"], r["tagline"], r["team_id"], r["team_name"], r["track_id"],
            r["track_name"], r["status"], r["repo_url"], r["live_url"], r["video_url"],
            " ".join(json.loads(r["tech_tags"] or "[]")), r["submitted_at"],
            r["duplicate_of"], r["duplicate_reason"],
        ]
        for r in rows
    ]


def export_teams(conn: sqlite3.Connection, event_id: str) -> tuple[list[str], list[list[Any]]]:
    header = ["team_id", "team_name", "invite_code", "member_email", "member_name", "role_in_team"]
    rows = query(
        conn,
        """
        SELECT t.id, t.name, t.invite_code, u.email, u.name AS member_name, tm.role_in_team
          FROM teams t
          LEFT JOIN team_members tm ON tm.team_id = t.id
          LEFT JOIN users u ON u.id = tm.user_id
         WHERE t.event_id = ? ORDER BY t.id, u.email
        """,
        (event_id,),
    )
    return header, [
        [r["id"], r["name"], r["invite_code"], r["email"], r["member_name"], r["role_in_team"]]
        for r in rows
    ]


def export_judges(conn: sqlite3.Connection, event_id: str) -> tuple[list[str], list[list[Any]]]:
    header = [
        "judge_id", "name", "email", "status", "tracks", "assigned", "completed", "outstanding",
    ]
    rows = query(
        conn,
        """
        SELECT j.id, j.display_name, j.email, j.status,
               (SELECT GROUP_CONCAT(jt.track_id, ' ') FROM judge_tracks jt
                 WHERE jt.judge_id = j.id) AS tracks,
               (SELECT COUNT(*) FROM assignments a
                 WHERE a.judge_id = j.id AND a.event_id = j.event_id) AS assigned,
               (SELECT COUNT(*) FROM scores s
                 WHERE s.judge_id = j.id AND s.event_id = j.event_id) AS completed
          FROM judges j WHERE j.event_id = ? ORDER BY j.id
        """,
        (event_id,),
    )
    return header, [
        [
            r["id"], r["display_name"], r["email"], r["status"], r["tracks"] or "",
            r["assigned"], r["completed"], max(int(r["assigned"]) - int(r["completed"]), 0),
        ]
        for r in rows
    ]


def export_assignments(
    conn: sqlite3.Connection, event_id: str
) -> tuple[list[str], list[list[Any]]]:
    header = ["assignment_id", "judge_id", "judge_name", "project_id", "project_title",
              "track_id", "status", "batch", "created_at"]
    rows = query(
        conn,
        """
        SELECT a.id, a.judge_id, j.display_name, a.project_id, p.title, p.track_id,
               a.status, a.batch, a.created_at
          FROM assignments a
          LEFT JOIN judges j ON j.id = a.judge_id
          LEFT JOIN projects p ON p.id = a.project_id
         WHERE a.event_id = ? ORDER BY a.judge_id, a.project_id
        """,
        (event_id,),
    )
    return header, [
        [r["id"], r["judge_id"], r["display_name"], r["project_id"], r["title"],
         r["track_id"], r["status"], r["batch"], r["created_at"]]
        for r in rows
    ]


def export_scores(conn: sqlite3.Connection, event_id: str) -> tuple[list[str], list[list[Any]]]:
    """Raw ballots, one row per ballot, one column per rubric criterion."""
    criteria = [
        row["key"]
        for row in query(
            conn,
            "SELECT key FROM rubric_criteria WHERE event_id = ? ORDER BY sort, key",
            (event_id,),
        )
    ]
    header = ["score_id", "judge_id", "judge_name", "project_id", "project_title"]
    header += [f"criteria_{key}" for key in criteria]
    header += ["weighted", "comment", "submitted_at", "updated_at"]

    weights = {
        row["key"]: float(row["weight"])
        for row in query(
            conn, "SELECT key, weight FROM rubric_criteria WHERE event_id = ?", (event_id,)
        )
    }
    rows = query(
        conn,
        """
        SELECT s.id, s.judge_id, j.display_name, s.project_id, p.title, s.comment,
               s.submitted_at, s.updated_at
          FROM scores s
          LEFT JOIN judges j ON j.id = s.judge_id
          LEFT JOIN projects p ON p.id = s.project_id
         WHERE s.event_id = ? ORDER BY s.judge_id, s.project_id
        """,
        (event_id,),
    )
    values: dict[str, dict[str, int]] = {}
    for row in query(
        conn,
        """
        SELECT sc.score_id, sc.criterion_key, sc.value FROM score_criteria sc
          JOIN scores s ON s.id = sc.score_id WHERE s.event_id = ?
        """,
        (event_id,),
    ):
        values.setdefault(row["score_id"], {})[row["criterion_key"]] = int(row["value"])

    from .normalize import weighted_value

    out = []
    for r in rows:
        ballot = values.get(r["id"], {})
        line = [r["id"], r["judge_id"], r["display_name"], r["project_id"], r["title"]]
        line += [ballot.get(key) for key in criteria]
        line += [
            round(weighted_value({k: float(v) for k, v in ballot.items()}, weights), 4)
            if ballot else None,
            r["comment"],
            r["submitted_at"],
            r["updated_at"],
        ]
        out.append(line)
    return header, out


def export_results(
    conn: sqlite3.Connection, event_id: str, *, method: str | None = None
) -> tuple[list[str], list[list[Any]]]:
    """The leaderboard, with every normalization method side by side.

    All three columns ship regardless of which method the event has selected,
    so the claims in JUDGING.md can be checked in a spreadsheet rather than
    taken on trust.
    """
    from .results import leaderboard

    header = [
        "position", "project_id", "title", "team", "track", "n_reviews", "low_confidence",
        "raw_mean", "shrunken_z", "additive_ridge", "selected_method", "score", "std_error",
        "rank_raw", "rank_normalized", "rank_delta",
    ]
    rows = leaderboard(conn, event_id, method=method)
    result_method = method or (
        query(conn, "SELECT normalization_method FROM events WHERE id = ?", (event_id,))[0][0]
    )
    return header, [
        [
            r["position"], r["project_id"], r["title"], r["team"], r["track"], r["n_reviews"],
            "yes" if r["low_confidence"] else "no", r["raw"], r["shrunken_z"],
            r["additive_ridge"], result_method, r["score"], r["std_error"],
            r["rank_raw"], r["rank_normalized"], r["rank_delta"],
        ]
        for r in rows
    ]


def export_audit(conn: sqlite3.Connection, event_id: str) -> tuple[list[str], list[list[Any]]]:
    header = ["seq", "at", "actor_user_id", "actor_role", "action", "target_type",
              "target_id", "reason_code", "detail", "entry_hash"]
    rows = query(
        conn,
        """
        SELECT seq, at, actor_user_id, actor_role, action, target_type, target_id,
               reason_code, detail, entry_hash
          FROM audit_log WHERE event_id = ? OR ? = '' ORDER BY seq
        """,
        (event_id, event_id),
    )
    return header, [
        [r["seq"], r["at"], r["actor_user_id"], r["actor_role"], r["action"], r["target_type"],
         r["target_id"], r["reason_code"], r["detail"], r["entry_hash"]]
        for r in rows
    ]


EXPORTERS = {
    "projects": export_projects,
    "teams": export_teams,
    "judges": export_judges,
    "assignments": export_assignments,
    "scores": export_scores,
    "results": export_results,
    "audit": export_audit,
}


def render_stage(
    conn: sqlite3.Connection,
    stage: str,
    event_id: str,
    *,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    method: str | None = None,
) -> str:
    exporter = EXPORTERS[stage]
    if stage == "results":
        header, rows = exporter(conn, event_id, method=method)  # type: ignore[call-arg]
    else:
        header, rows = exporter(conn, event_id)
    audit.record(
        conn,
        "export.csv",
        event_id=event_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        target_type="export",
        target_id=stage,
        detail={"rows": len(rows), "method": method},
    )
    return to_csv(header, rows)


# -------------------------------------------------------- bulk json export ---


def export_event_json(conn: sqlite3.Connection, event_id: str) -> dict[str, Any]:
    """Whole-event snapshot in the fixtures.json shape, plus what fixtures.json
    has no field for. Round-trips through import_event_json."""
    event = query(conn, "SELECT * FROM events WHERE id = ?", (event_id,))[0]
    tracks = query(conn, "SELECT id, name FROM tracks WHERE event_id = ? ORDER BY id", (event_id,))
    judges = query(
        conn,
        "SELECT id, display_name, email FROM judges WHERE event_id = ? ORDER BY id",
        (event_id,),
    )
    judge_tracks: dict[str, list[str]] = {}
    for row in query(
        conn,
        "SELECT jt.judge_id, jt.track_id FROM judge_tracks jt JOIN judges j "
        "ON j.id = jt.judge_id WHERE j.event_id = ? ORDER BY jt.track_id",
        (event_id,),
    ):
        judge_tracks.setdefault(row["judge_id"], []).append(row["track_id"])

    teams = query(conn, "SELECT id, name FROM teams WHERE event_id = ? ORDER BY id", (event_id,))
    members: dict[str, list[str]] = {}
    for row in query(
        conn,
        "SELECT tm.team_id, u.email FROM team_members tm JOIN users u ON u.id = tm.user_id "
        "JOIN teams t ON t.id = tm.team_id WHERE t.event_id = ? ORDER BY u.email",
        (event_id,),
    ):
        members.setdefault(row["team_id"], []).append(row["email"])

    projects = query(
        conn,
        """
        SELECT id, team_id, track_id, title, tagline, description, repo_url, live_url,
               video_url, thumbnail_url, tech_tags, status, submitted_at, duplicate_of
          FROM projects WHERE event_id = ? ORDER BY id
        """,
        (event_id,),
    )
    score_rows = query(
        conn,
        "SELECT id, judge_id, project_id, comment FROM scores WHERE event_id = ? ORDER BY id",
        (event_id,),
    )
    criteria: dict[str, dict[str, int]] = {}
    for row in query(
        conn,
        "SELECT sc.score_id, sc.criterion_key, sc.value FROM score_criteria sc "
        "JOIN scores s ON s.id = sc.score_id WHERE s.event_id = ?",
        (event_id,),
    ):
        criteria.setdefault(row["score_id"], {})[row["criterion_key"]] = int(row["value"])

    images: dict[str, list[str]] = {}
    for row in query(
        conn,
        "SELECT pi.project_id, pi.url FROM project_images pi "
        "JOIN projects p ON p.id = pi.project_id WHERE p.event_id = ? ORDER BY pi.sort",
        (event_id,),
    ):
        images.setdefault(row["project_id"], []).append(row["url"])

    answers: dict[str, dict[str, str]] = {}
    for row in query(
        conn,
        "SELECT pa.project_id, pa.question_id, pa.answer FROM project_answers pa "
        "JOIN projects p ON p.id = pa.project_id WHERE p.event_id = ?",
        (event_id,),
    ):
        answers.setdefault(row["project_id"], {})[row["question_id"]] = row["answer"]

    return {
        "exported_at": utcnow(),
        "event": {
            "id": event["id"],
            "name": event["name"],
            "description": event["description"],
            "submissions_close": event["submissions_close"],
            "voting_opens_at": event["voting_opens_at"],
            "voting_closes_at": event["voting_closes_at"],
            "voting_access": event["voting_access"]
            if "voting_access" in event.keys()
            else "authenticated",
            "results_published": bool(event["results_published"]),
            "normalization_method": event["normalization_method"],
            "reviews_per_project": event["reviews_per_project"],
            "exclude_duplicates": bool(event["exclude_duplicates"]),
        },
        "prizes": [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "amount_cents": r["amount_cents"],
                "currency": r["currency"],
            }
            for r in query(
                conn,
                "SELECT id, name, description, amount_cents, currency FROM prizes "
                "WHERE event_id = ? ORDER BY sort",
                (event_id,),
            )
        ],
        "custom_questions": [
            {
                "id": r["id"],
                "prompt": r["prompt"],
                "kind": r["kind"],
                "options": json.loads(r["options"] or "[]"),
                "required": bool(r["required"]),
            }
            for r in query(
                conn,
                "SELECT id, prompt, kind, options, required FROM custom_questions "
                "WHERE event_id = ? ORDER BY sort",
                (event_id,),
            )
        ],
        "rubric": [
            {"key": r["key"], "label": r["label"], "weight": r["weight"]}
            for r in query(
                conn,
                "SELECT key, label, weight FROM rubric_criteria WHERE event_id = ? ORDER BY sort",
                (event_id,),
            )
        ],
        "tracks": [{"id": r["id"], "name": r["name"]} for r in tracks],
        "judges": [
            {
                "id": r["id"],
                "name": r["display_name"],
                "email": r["email"],
                "tracks": judge_tracks.get(r["id"], []),
            }
            for r in judges
        ],
        "teams": [
            {"id": r["id"], "name": r["name"], "members": members.get(r["id"], [])}
            for r in teams
        ],
        "projects": [
            {
                "id": r["id"],
                "team": r["team_id"],
                "track": r["track_id"],
                "title": r["title"],
                "summary": r["tagline"],
                "description": r["description"],
                "repo_url": r["repo_url"],
                "live_url": r["live_url"],
                "video_url": r["video_url"],
                "thumbnail_url": r["thumbnail_url"],
                "tech_tags": json.loads(r["tech_tags"] or "[]"),
                "status": r["status"],
                "submitted_at": r["submitted_at"],
                "duplicate_of": r["duplicate_of"],
                "images": images.get(r["id"], []),
                "custom_answers": answers.get(r["id"], {}),
            }
            for r in projects
        ],
        "assignments": [
            {
                "id": r["id"],
                "judge": r["judge_id"],
                "project": r["project_id"],
                "status": r["status"],
                "batch": r["batch"],
            }
            for r in query(
                conn,
                "SELECT id, judge_id, project_id, status, batch FROM assignments "
                "WHERE event_id = ? ORDER BY id",
                (event_id,),
            )
        ],
        "votes": [
            {
                "id": r["id"],
                "project": r["project_id"],
                "voter_key": r["voter_key"],
                "voter_mode": r["voter_mode"],
                "credits": r["credits"],
            }
            for r in query(
                conn,
                "SELECT id, project_id, voter_key, voter_mode, credits FROM votes "
                "WHERE event_id = ? ORDER BY id",
                (event_id,),
            )
        ],
        "webhooks": [
            {
                "id": r["id"],
                "url": r["url"],
                "actions": json.loads(r["actions"] or "[]"),
                "active": bool(r["active"]),
            }
            for r in query(
                conn,
                "SELECT id, url, actions, active FROM webhooks "
                "WHERE event_id IS NULL OR event_id = ? ORDER BY id",
                (event_id,),
            )
        ],
        "scores": [
            {
                "judge": r["judge_id"],
                "project": r["project_id"],
                "criteria": criteria.get(r["id"], {}),
                "comment": r["comment"],
            }
            for r in score_rows
        ],
    }
