"""Load fixtures.json into the portal.

Two rules govern this file.

Lossless: every record in fixtures.json becomes a row, including the duplicate
submission. Detection happens after insertion and annotates; it never drops.
An organizer cannot adjudicate a duplicate that the importer threw away.

Idempotent: seeding is an upsert keyed on the fixture ids, so `docker compose
up` on an existing volume converges instead of failing on a unique constraint.
That is what makes restarting the container safe, and it is asserted in
tests/test_adversarial.py.

The fixture ids are used verbatim as primary keys -- prj_07 in the file is
prj_07 in the database -- so that a judge comparing the two is comparing the
same object and not a mapping table.
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from . import audit
from .assignment import generate_assignments
from .db import query, query_one, scalar, utcnow
from .security import hash_password, issue_session

# The dev logins from spec.md, reproduced exactly so that the .dogfood.toml in
# the spec's example is the .dogfood.toml in this repo. Deterministic on
# purpose: a committed acceptance report has to stay reproducible on a
# stranger's laptop weeks later. Gated behind DOGFOOD_DEV_TOKENS.
DEV_TOKENS = {
    "organizer": "org_7f2a",
    "judge_a": "jdg_a_91bc",
    "judge_b": "jdg_b_44de",
    "participant": "prt_2e88",
}

# judge_a and judge_b are bound to real fixture judges, so `peer_scores` in
# .dogfood.toml points at a url that genuinely returns another judge's ballots
# rather than at a route that happens to 404.
JUDGE_A_FIXTURE_ID = "jdg_01"
JUDGE_B_FIXTURE_ID = "jdg_02"

DEV_PASSWORD = "dogfood"

DEMO_EVENT_ID = "evt_demo"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "event"


def normalise_title(title: str) -> str:
    """Whitespace- and case-insensitive title key, for duplicate detection."""
    return " ".join((title or "").lower().split())


def load_fixture_file(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------- users ---


def _upsert_user(
    conn: sqlite3.Connection,
    user_id: str,
    email: str,
    name: str,
    role: str,
    *,
    password: str | None = None,
) -> str:
    """Insert or update a user, keyed on email so re-seeding is stable.

    Roles are not downgraded on re-seed: a user who is both a team member and
    an organizer keeps the stronger role.
    """
    existing = query_one(conn, "SELECT id, role FROM users WHERE lower(email) = ?", (email.lower(),))
    rank = {"visitor": 0, "participant": 1, "judge": 2, "organizer": 3, "admin": 4}
    if existing:
        if rank.get(role, 0) > rank.get(existing["role"], 0):
            conn.execute("UPDATE users SET role = ?, name = ? WHERE id = ?",
                         (role, name, existing["id"]))
        return str(existing["id"])

    password_hash = password_salt = password_kdf = None
    if password:
        password_hash, password_salt, password_kdf = hash_password(password)
    conn.execute(
        """
        INSERT INTO users (id, email, name, role, password_hash, password_salt,
                           password_kdf, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, email, name, role, password_hash, password_salt, password_kdf, utcnow()),
    )
    return user_id


# ------------------------------------------------------- duplicate detection ---


def detect_duplicates(conn: sqlite3.Connection, event_id: str) -> list[dict[str, Any]]:
    """Flag re-submissions of the same work by the same team.

    Two signals, both of which fire on the fixture's prj_07 / prj_41 pair:
    identical (team, normalised title), and identical repository url. The
    earliest submission is treated as the original; later ones point at it.

    The flag is advisory. Flagged projects stay in the gallery, stay in the
    database, and keep their ballots in the calibration data -- they are only
    excluded from the ranking, and only while the event's exclude_duplicates
    switch is on.
    """
    projects = query(
        conn,
        """
        SELECT id, team_id, title, repo_url, submitted_at, created_at, status
          FROM projects WHERE event_id = ?
         ORDER BY COALESCE(submitted_at, created_at), id
        """,
        (event_id,),
    )

    by_team_title: dict[tuple[str, str], str] = {}
    by_repo: dict[tuple[str, str], str] = {}
    found: list[dict[str, Any]] = []

    for project in projects:
        pid = project["id"]
        title_key = (project["team_id"], normalise_title(project["title"]))
        repo = (project["repo_url"] or "").strip().rstrip("/").lower()
        repo_key = (project["team_id"], repo)

        original = by_team_title.get(title_key)
        reason = "same team and identical title" if original else None
        if original is None and repo:
            original = by_repo.get(repo_key)
            reason = "same team and identical repository url" if original else None

        if original and original != pid:
            found.append({"project_id": pid, "duplicate_of": original, "reason": reason})
            conn.execute(
                """
                UPDATE projects
                   SET duplicate_of = ?, duplicate_reason = ?,
                       status = CASE WHEN status = 'submitted' THEN 'flagged_duplicate'
                                     ELSE status END,
                       updated_at = ?
                 WHERE id = ?
                """,
                (original, reason, utcnow(), pid),
            )
            audit.record(
                conn,
                "project.flagged_duplicate",
                event_id=event_id,
                actor_role="system",
                target_type="project",
                target_id=pid,
                reason_code="duplicate_detected",
                detail={"duplicate_of": original, "signal": reason},
            )
        else:
            by_team_title.setdefault(title_key, pid)
            if repo:
                by_repo.setdefault(repo_key, pid)

    return found


def duplicate_report(conn: sqlite3.Connection, event_id: str) -> list[dict[str, Any]]:
    """Duplicates with the cost of each one in review slots.

    The second-order effect is the interesting one: in the fixture data three
    judges reviewed both copies of the same project, so one team absorbed nine
    review slots out of 126.
    """
    rows = query(
        conn,
        """
        SELECT p.id, p.title, p.team_id, p.duplicate_of, p.duplicate_reason,
               p.submitted_at, o.submitted_at AS original_submitted_at
          FROM projects p LEFT JOIN projects o ON o.id = p.duplicate_of
         WHERE p.event_id = ? AND p.duplicate_of IS NOT NULL
         ORDER BY p.id
        """,
        (event_id,),
    )
    report = []
    for row in rows:
        dup_judges = {
            r["judge_id"]
            for r in query(conn, "SELECT judge_id FROM scores WHERE project_id = ?", (row["id"],))
        }
        orig_judges = {
            r["judge_id"]
            for r in query(
                conn, "SELECT judge_id FROM scores WHERE project_id = ?", (row["duplicate_of"],)
            )
        }
        report.append(
            {
                "project_id": row["id"],
                "title": row["title"],
                "team_id": row["team_id"],
                "duplicate_of": row["duplicate_of"],
                "reason": row["duplicate_reason"],
                "submitted_at": row["submitted_at"],
                "original_submitted_at": row["original_submitted_at"],
                "reviews_on_duplicate": len(dup_judges),
                "reviews_on_original": len(orig_judges),
                "review_slots_consumed": len(dup_judges) + len(orig_judges),
                "judges_who_reviewed_both": sorted(dup_judges & orig_judges),
            }
        )
    return report


# -------------------------------------------------------------------- seed ---


def seed(
    conn: sqlite3.Connection,
    fixtures: dict[str, Any],
    *,
    dev_tokens: bool = True,
) -> dict[str, Any]:
    """Load the fixture event, then derive assignments and flag duplicates."""
    now = utcnow()
    event = fixtures["event"]
    event_id = event["id"]

    conn.execute(
        """
        INSERT INTO events (id, name, slug, description, submissions_close,
                            reviews_per_project, is_fixture, created_at)
        VALUES (?, ?, ?, ?, ?, 3, 1, ?)
        ON CONFLICT (id) DO UPDATE SET
            name = excluded.name,
            submissions_close = excluded.submissions_close
        """,
        (
            event_id,
            event["name"],
            _slug(event["name"]),
            "Fixture event published with the DOGFOOD 2026 spec. "
            "Submissions closed at the fixture deadline.",
            event.get("submissions_close"),
            now,
        ),
    )

    for index, prize in enumerate(
        [("Grand prize", 80000), ("Runner-up", 50000), ("Best judging engine", 10000)]
    ):
        conn.execute(
            """
            INSERT INTO prizes (id, event_id, name, amount_cents, sort)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET name = excluded.name
            """,
            (f"prz_{event_id}_{index + 1}", event_id, prize[0], prize[1], index),
        )

    for track in fixtures.get("tracks", []):
        conn.execute(
            """
            INSERT INTO tracks (id, event_id, name) VALUES (?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET name = excluded.name
            """,
            (track["id"], event_id, track["name"]),
        )

    # --- rubric ----------------------------------------------------------
    # Criteria are taken from the fixture ballots. Weights start equal
    # because fixtures.json does not state any; the organizer can reweight
    # them, which is the whole point of the table.
    criteria_keys: list[str] = []
    for score in fixtures.get("scores", []):
        for key in score.get("criteria", {}):
            if key not in criteria_keys:
                criteria_keys.append(key)
    for index, key in enumerate(criteria_keys):
        conn.execute(
            """
            INSERT INTO rubric_criteria (id, event_id, key, label, weight, sort)
            VALUES (?, ?, ?, ?, 1.0, ?)
            ON CONFLICT (event_id, key) DO UPDATE SET label = excluded.label
            """,
            (f"crt_{event_id}_{key}", event_id, key, key.replace("_", " ").title(), index),
        )

    # --- teams and participants -------------------------------------------
    for team in fixtures.get("teams", []):
        conn.execute(
            """
            INSERT INTO teams (id, event_id, name, invite_code, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET name = excluded.name
            """,
            (team["id"], event_id, team["name"], f"invite-{team['id']}", now),
        )
        for position, email in enumerate(team.get("members", [])):
            local = email.split("@")[0]
            user_id = _upsert_user(
                conn,
                f"usr_{team['id']}_{position + 1}",
                email,
                local.replace(".", " ").title(),
                "participant",
                password=DEV_PASSWORD,
            )
            conn.execute(
                """
                INSERT INTO team_members (team_id, user_id, role_in_team, joined_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (team_id, user_id) DO NOTHING
                """,
                (team["id"], user_id, "owner" if position == 0 else "member", now),
            )

    # --- judges -----------------------------------------------------------
    for judge in fixtures.get("judges", []):
        user_id = _upsert_user(
            conn,
            f"usr_{judge['id']}",
            judge["email"],
            judge["name"],
            "judge",
            password=DEV_PASSWORD,
        )
        conn.execute(
            """
            INSERT INTO judges (id, event_id, user_id, display_name, email, status,
                                invite_code, invited_at, accepted_at)
            VALUES (?, ?, ?, ?, ?, 'accepted', ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                display_name = excluded.display_name, email = excluded.email
            """,
            (
                judge["id"],
                event_id,
                user_id,
                judge["name"],
                judge["email"],
                f"judge-invite-{judge['id']}",
                now,
                now,
            ),
        )
        for track_id in judge.get("tracks", []):
            conn.execute(
                "INSERT INTO judge_tracks (judge_id, track_id) VALUES (?, ?) "
                "ON CONFLICT DO NOTHING",
                (judge["id"], track_id),
            )

    # --- projects ---------------------------------------------------------
    for project in fixtures.get("projects", []):
        conn.execute(
            """
            INSERT INTO projects (id, event_id, team_id, track_id, title, tagline,
                                  description, repo_url, tech_tags, status,
                                  submitted_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', 'submitted', ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                title = excluded.title,
                tagline = excluded.tagline,
                track_id = excluded.track_id,
                repo_url = excluded.repo_url,
                submitted_at = excluded.submitted_at,
                updated_at = excluded.updated_at
            """,
            (
                project["id"],
                event_id,
                project["team"],
                project.get("track"),
                project["title"],
                project.get("summary", ""),
                project.get("summary", ""),
                project.get("repo_url"),
                project.get("submitted_at"),
                project.get("submitted_at") or now,
                now,
            ),
        )

    # --- ballots ----------------------------------------------------------
    for score in fixtures.get("scores", []):
        score_id = f"scr_{score['judge']}_{score['project']}"
        conn.execute(
            """
            INSERT INTO scores (id, event_id, judge_id, project_id, comment,
                                submitted_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (event_id, judge_id, project_id) DO UPDATE SET
                comment = excluded.comment, updated_at = excluded.updated_at
            """,
            (
                score_id,
                event_id,
                score["judge"],
                score["project"],
                score.get("comment", ""),
                now,
                now,
            ),
        )
        for key, value in (score.get("criteria") or {}).items():
            conn.execute(
                """
                INSERT INTO score_criteria (score_id, criterion_key, value)
                VALUES (?, ?, ?)
                ON CONFLICT (score_id, criterion_key) DO UPDATE SET value = excluded.value
                """,
                (score_id, key, int(value)),
            )
        # A cast ballot implies the assignment that produced it.
        conn.execute(
            """
            INSERT INTO assignments (id, event_id, judge_id, project_id, status,
                                     batch, created_at)
            VALUES (?, ?, ?, ?, 'completed', 1, ?)
            ON CONFLICT (event_id, judge_id, project_id)
              DO UPDATE SET status = 'completed'
            """,
            (
                f"asg_{event_id}_{score['judge']}_{score['project']}",
                event_id,
                score["judge"],
                score["project"],
                now,
            ),
        )

    duplicates = detect_duplicates(conn, event_id)
    plan = generate_assignments(conn, event_id, actor_role="system")

    demo = _seed_demo_event(conn)
    logins = _seed_operators(conn, dev_tokens=dev_tokens)

    counts = {
        "tracks": scalar(conn, "SELECT COUNT(*) FROM tracks WHERE event_id = ?", (event_id,)),
        "teams": scalar(conn, "SELECT COUNT(*) FROM teams WHERE event_id = ?", (event_id,)),
        "judges": scalar(conn, "SELECT COUNT(*) FROM judges WHERE event_id = ?", (event_id,)),
        "projects": scalar(conn, "SELECT COUNT(*) FROM projects WHERE event_id = ?", (event_id,)),
        "scores": scalar(conn, "SELECT COUNT(*) FROM scores WHERE event_id = ?", (event_id,)),
        "assignments": scalar(
            conn, "SELECT COUNT(*) FROM assignments WHERE event_id = ?", (event_id,)
        ),
    }

    audit.record(
        conn,
        "fixtures.seeded",
        event_id=event_id,
        actor_role="system",
        target_type="event",
        target_id=event_id,
        detail={
            "counts": counts,
            "duplicates_flagged": duplicates,
            "assignments_created": plan.created,
            "assignments_unfillable": plan.unfillable,
        },
    )

    return {
        "event_id": event_id,
        "demo_event_id": demo,
        "counts": counts,
        "duplicates": duplicates,
        "assignment": {
            "created": plan.created,
            "skipped_duplicates": plan.skipped_duplicates,
            "unfillable": plan.unfillable,
        },
        "logins": logins,
    }


def _seed_demo_event(conn: sqlite3.Connection) -> str:
    """A second, open event.

    The fixture event's deadline is in the past, which is correct and is what
    the acceptance suite checks -- but it also makes draft-and-edit
    unreachable, so there would be no way to demonstrate the submission
    lifecycle. This event exists for that, holds no fixture data, and is named
    so nobody mistakes it for fixture data.
    """
    now = utcnow()
    conn.execute(
        """
        INSERT INTO events (id, name, slug, description, submissions_close,
                            voting_opens_at, voting_closes_at, reviews_per_project,
                            is_fixture, created_at)
        VALUES (?, ?, ?, ?, '2099-01-01T00:00:00Z', ?, '2099-01-01T00:00:00Z', 3, 0, ?)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            DEMO_EVENT_ID,
            "Deadline Demo (not fixture data)",
            "deadline-demo",
            "An open event, so the submit-edit-deadline lifecycle can be exercised. "
            "Contains no fixture projects.",
            now,
            now,
        ),
    )
    conn.execute(
        "INSERT INTO tracks (id, event_id, name) VALUES (?, ?, 'General') "
        "ON CONFLICT (id) DO NOTHING",
        (f"trk_{DEMO_EVENT_ID}_general", DEMO_EVENT_ID),
    )
    for key, label, weight in (
        ("functionality", "Functionality", 2.0),
        ("quality", "Quality", 1.5),
        ("innovation", "Innovation", 1.0),
    ):
        # Deliberately unequal, so the weighted rubric is visibly weighted
        # somewhere in the seeded state rather than only in the docs.
        conn.execute(
            """
            INSERT INTO rubric_criteria (id, event_id, key, label, weight, sort)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT (event_id, key) DO NOTHING
            """,
            (f"crt_{DEMO_EVENT_ID}_{key}", DEMO_EVENT_ID, key, label, weight),
        )
    return DEMO_EVENT_ID


def _seed_operators(conn: sqlite3.Connection, *, dev_tokens: bool) -> list[dict[str, str]]:
    """Create the four roles the acceptance suite needs headers for."""
    now = utcnow()

    organizer_id = _upsert_user(
        conn, "usr_organizer", "organizer@dogfood.local", "Event Organizer", "organizer",
        password=DEV_PASSWORD,
    )
    admin_id = _upsert_user(
        conn, "usr_admin", "admin@dogfood.local", "Platform Admin", "admin",
        password=DEV_PASSWORD,
    )

    judge_a = query_one(conn, "SELECT user_id FROM judges WHERE id = ?", (JUDGE_A_FIXTURE_ID,))
    judge_b = query_one(conn, "SELECT user_id FROM judges WHERE id = ?", (JUDGE_B_FIXTURE_ID,))

    # The participant is a real fixture team member, so their team, project and
    # permissions are the fixture's rather than a synthetic extra.
    participant = query_one(
        conn,
        """
        SELECT u.id FROM users u
          JOIN team_members tm ON tm.user_id = u.id
          JOIN teams t ON t.id = tm.team_id
         WHERE u.role = 'participant' AND t.event_id = 'evt_01'
         ORDER BY u.id LIMIT 1
        """,
    )
    participant_id = participant["id"] if participant else _upsert_user(
        conn, "usr_participant", "participant@dogfood.local", "Participant", "participant",
        password=DEV_PASSWORD,
    )

    # Also put the participant on a team in the open demo event, so the
    # submit-edit-deadline lifecycle is reachable without setup.
    conn.execute(
        """
        INSERT INTO teams (id, event_id, name, invite_code, created_by, created_at)
        VALUES (?, ?, 'Demo Team', 'invite-demo-team', ?, ?)
        ON CONFLICT (id) DO NOTHING
        """,
        (f"tm_{DEMO_EVENT_ID}_demo", DEMO_EVENT_ID, participant_id, now),
    )
    conn.execute(
        """
        INSERT INTO team_members (team_id, user_id, role_in_team, joined_at)
        VALUES (?, ?, 'owner', ?) ON CONFLICT DO NOTHING
        """,
        (f"tm_{DEMO_EVENT_ID}_demo", participant_id, now),
    )

    wanted = {
        "organizer": organizer_id,
        "judge_a": judge_a["user_id"] if judge_a else organizer_id,
        "judge_b": judge_b["user_id"] if judge_b else organizer_id,
        "participant": participant_id,
        "admin": admin_id,
    }

    logins: list[dict[str, str]] = []
    for label, user_id in wanted.items():
        token = DEV_TOKENS.get(label)
        if not dev_tokens or token is None:
            existing = query_one(
                conn, "SELECT token FROM sessions WHERE user_id = ? AND label = ?", (user_id, label)
            )
            token = existing["token"] if existing else secrets.token_urlsafe(24)
        issue_session(conn, user_id, token=token, label=label)
        row = query_one(conn, "SELECT email, role FROM users WHERE id = ?", (user_id,))
        logins.append(
            {
                "label": label,
                "user_id": user_id,
                "email": row["email"] if row else "",
                "role": row["role"] if row else "",
                "header": f"Cookie: df_session={token}",
                "token": token,
            }
        )
    return logins
