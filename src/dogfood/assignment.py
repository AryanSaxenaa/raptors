"""Judge assignment.

Constraints, in priority order:

  1. Track scope. A judge is only ever assigned inside their own tracks. The
     fixture data holds this invariant exactly -- zero of its 126 ballots cross
     a track boundary -- and the T2 rule says a track judge must never see
     another track, so the assigner must not be the thing that breaks it.
  2. No conflict of interest. A judge is never assigned a project belonging to
     a team they are a member of.
  3. Coverage. Every eligible project reaches the event's reviews_per_project.
  4. Balance. Among eligible judges, the least loaded wins. Ties break on judge
     id, so the same input always produces the same assignment and the result
     is testable.

Projects flagged as duplicates are skipped when topping up coverage. In the
fixture data three judges each reviewed both copies of `Dry Harbour`, so one
team consumed 9 of the event's 126 review slots; continuing to schedule reviews
against a known duplicate spends a scarce resource on a project that will not
be ranked.

Track capacity is reported rather than silently absorbed: trk_01 and trk_08
have 3 judges for 6 projects each while trk_04 has 8 judges for 5 projects, so
a perfectly balanced global load is not achievable and an organizer should see
where the shortfall is.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from . import audit
from .db import query, utcnow


@dataclass
class AssignmentPlan:
    created: int = 0
    skipped_duplicates: list[str] = field(default_factory=list)
    unfillable: list[dict[str, Any]] = field(default_factory=list)
    per_judge: dict[str, int] = field(default_factory=dict)


def track_capacity(conn: sqlite3.Connection, event_id: str) -> list[dict[str, Any]]:
    """Judges and projects per track, so a shortfall is visible before it bites."""
    rows = query(
        conn,
        """
        SELECT t.id AS track_id, t.name,
               (SELECT COUNT(*) FROM judge_tracks jt
                  JOIN judges j ON j.id = jt.judge_id
                 WHERE jt.track_id = t.id AND j.status != 'removed') AS judges,
               (SELECT COUNT(*) FROM projects p
                 WHERE p.track_id = t.id AND p.status IN ('submitted', 'flagged_duplicate')
               ) AS projects
        FROM tracks t WHERE t.event_id = ? ORDER BY t.id
        """,
        (event_id,),
    )
    out = []
    for row in rows:
        target = int(row["projects"]) * _reviews_target(conn, event_id)
        capacity_note = None
        if row["judges"] == 0 and row["projects"] > 0:
            capacity_note = "no judges assigned to this track"
        elif row["judges"] and target / max(row["judges"], 1) > 10:
            capacity_note = "each judge in this track would carry more than 10 reviews"
        out.append(
            {
                "track_id": row["track_id"],
                "name": row["name"],
                "judges": int(row["judges"]),
                "projects": int(row["projects"]),
                "reviews_needed": target,
                "note": capacity_note,
            }
        )
    return out


def _reviews_target(conn: sqlite3.Connection, event_id: str) -> int:
    row = conn.execute(
        "SELECT reviews_per_project FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    return int(row["reviews_per_project"]) if row else 3


def generate_assignments(
    conn: sqlite3.Connection,
    event_id: str,
    *,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
) -> AssignmentPlan:
    """Top every eligible project up to the event's review target.

    Existing assignments are preserved, so this is safe to run repeatedly as
    projects arrive: it only ever adds what is missing.
    """
    target = _reviews_target(conn, event_id)
    plan = AssignmentPlan()

    judges = query(
        conn,
        "SELECT id, user_id FROM judges WHERE event_id = ? AND status != 'removed' ORDER BY id",
        (event_id,),
    )
    if not judges:
        return plan

    judge_tracks: dict[str, set[str]] = defaultdict(set)
    for row in query(
        conn,
        """
        SELECT jt.judge_id, jt.track_id FROM judge_tracks jt
          JOIN judges j ON j.id = jt.judge_id
         WHERE j.event_id = ?
        """,
        (event_id,),
    ):
        judge_tracks[row["judge_id"]].add(row["track_id"])

    # Team membership of each judge's user, for the conflict-of-interest rule.
    judge_teams: dict[str, set[str]] = defaultdict(set)
    for row in query(
        conn,
        """
        SELECT j.id AS judge_id, tm.team_id
          FROM judges j JOIN team_members tm ON tm.user_id = j.user_id
         WHERE j.event_id = ?
        """,
        (event_id,),
    ):
        judge_teams[row["judge_id"]].add(row["team_id"])

    load: dict[str, int] = {row["id"]: 0 for row in judges}
    assigned_to: dict[str, set[str]] = defaultdict(set)
    for row in query(
        conn,
        "SELECT judge_id, project_id FROM assignments WHERE event_id = ?",
        (event_id,),
    ):
        load[row["judge_id"]] = load.get(row["judge_id"], 0) + 1
        assigned_to[row["project_id"]].add(row["judge_id"])

    # A cast ballot counts as coverage even where no assignment row exists,
    # which is the state fixtures.json arrives in.
    for row in query(
        conn, "SELECT judge_id, project_id FROM scores WHERE event_id = ?", (event_id,)
    ):
        assigned_to[row["project_id"]].add(row["judge_id"])

    projects = query(
        conn,
        """
        SELECT id, team_id, track_id, status, duplicate_of
          FROM projects
         WHERE event_id = ? AND status IN ('submitted', 'flagged_duplicate')
         ORDER BY id
        """,
        (event_id,),
    )

    # Least-covered first, so a partially reviewed event converges on coverage
    # rather than piling reviews onto whichever project sorts first.
    ordered = sorted(projects, key=lambda p: (len(assigned_to[p["id"]]), p["id"]))

    now = utcnow()
    for project in ordered:
        if project["duplicate_of"] or project["status"] == "flagged_duplicate":
            plan.skipped_duplicates.append(project["id"])
            continue
        needed = target - len(assigned_to[project["id"]])
        if needed <= 0:
            continue
        for _ in range(needed):
            eligible = [
                row["id"]
                for row in judges
                if (project["track_id"] is None or project["track_id"] in judge_tracks[row["id"]])
                and row["id"] not in assigned_to[project["id"]]
                and project["team_id"] not in judge_teams[row["id"]]
            ]
            if not eligible:
                plan.unfillable.append(
                    {
                        "project_id": project["id"],
                        "track_id": project["track_id"],
                        "have": len(assigned_to[project["id"]]),
                        "want": target,
                        "reason": "no eligible judge left in this track",
                    }
                )
                break
            chosen = min(eligible, key=lambda jid: (load[jid], jid))
            conn.execute(
                """
                INSERT INTO assignments (id, event_id, judge_id, project_id, status,
                                         batch, created_at)
                VALUES (?, ?, ?, ?, 'pending', 1, ?)
                ON CONFLICT (event_id, judge_id, project_id) DO NOTHING
                """,
                (
                    f"asg_{event_id}_{chosen}_{project['id']}",
                    event_id,
                    chosen,
                    project["id"],
                    now,
                ),
            )
            assigned_to[project["id"]].add(chosen)
            load[chosen] += 1
            plan.created += 1

    plan.per_judge = dict(sorted(load.items()))
    audit.record(
        conn,
        "assignment.generated",
        event_id=event_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        target_type="event",
        target_id=event_id,
        detail={
            "created": plan.created,
            "target_reviews_per_project": target,
            "skipped_duplicates": plan.skipped_duplicates,
            "unfillable": plan.unfillable,
        },
    )
    return plan


def progress(conn: sqlite3.Connection, event_id: str) -> dict[str, Any]:
    """The organizer's live view: who has not started, and what is under-reviewed."""
    target = _reviews_target(conn, event_id)

    judge_rows = query(
        conn,
        """
        SELECT j.id, j.display_name, j.email, j.status,
               (SELECT COUNT(*) FROM assignments a
                 WHERE a.judge_id = j.id AND a.event_id = j.event_id) AS assigned,
               (SELECT COUNT(*) FROM scores s
                 WHERE s.judge_id = j.id AND s.event_id = j.event_id) AS completed
          FROM judges j
         WHERE j.event_id = ? AND j.status != 'removed'
         ORDER BY j.id
        """,
        (event_id,),
    )
    judges = []
    not_started = 0
    for row in judge_rows:
        assigned = int(row["assigned"])
        completed = int(row["completed"])
        outstanding = max(assigned - completed, 0)
        if completed == 0:
            not_started += 1
        judges.append(
            {
                "judge_id": row["id"],
                "name": row["display_name"],
                "email": row["email"],
                "assigned": assigned,
                "completed": completed,
                "outstanding": outstanding,
                "percent": round(100.0 * completed / assigned, 1) if assigned else None,
                "started": completed > 0,
            }
        )

    project_rows = query(
        conn,
        """
        SELECT p.id, p.title, p.status, p.duplicate_of, p.track_id,
               (SELECT COUNT(*) FROM scores s
                 WHERE s.project_id = p.id AND s.event_id = p.event_id) AS reviews
          FROM projects p
         WHERE p.event_id = ? AND p.status IN ('submitted', 'flagged_duplicate')
         ORDER BY p.id
        """,
        (event_id,),
    )
    under_reviewed = []
    review_histogram: dict[int, int] = defaultdict(int)
    for row in project_rows:
        reviews = int(row["reviews"])
        review_histogram[reviews] += 1
        if reviews < target and not row["duplicate_of"]:
            under_reviewed.append(
                {
                    "project_id": row["id"],
                    "title": row["title"],
                    "track_id": row["track_id"],
                    "reviews": reviews,
                    "short_by": target - reviews,
                }
            )

    total_assigned = sum(j["assigned"] for j in judges)
    total_completed = sum(j["completed"] for j in judges)
    return {
        "event_id": event_id,
        "reviews_per_project": target,
        "judges": judges,
        "judges_not_started": not_started,
        "assignments_total": total_assigned,
        "assignments_completed": total_completed,
        "percent_complete": (
            round(100.0 * total_completed / total_assigned, 1) if total_assigned else None
        ),
        "under_reviewed": under_reviewed,
        "reviews_per_project_histogram": dict(sorted(review_histogram.items())),
        "track_capacity": track_capacity(conn, event_id),
    }
