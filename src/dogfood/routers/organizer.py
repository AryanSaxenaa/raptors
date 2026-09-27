"""Organizer views: progress, results, duplicates, audit, exports and imports.

Everything here sits behind a capability from the role matrix: AGGREGATE for
progress and results, AUDIT_LOG for the trail. A judge holding only OWN_SCORES
is refused, which is the "Aggregate" and "Audit log" columns of the published
matrix.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, Field

from .. import assignment, audit, exports, normalize, records, results, seed
from ..db import query, query_one, transaction
from ..deps import Conn, Who, default_event_id, get_event
from ..errors import ApiError
from ..security import (
    Capability,
    Operation,
    has_capability,
    require_capability,
    require_operation,
)

router = APIRouter(prefix="/api", tags=["organizer"])


class DuplicateDecision(BaseModel):
    model_config = {"extra": "forbid"}
    action: str = Field(pattern=r"^(confirm|dismiss)$")
    note: str = Field(default="", max_length=1000)


@router.get("/organizer/progress", summary="Live judging progress")
def get_progress(conn: Conn, who: Who, event_id: str | None = None) -> dict[str, Any]:
    event_id = event_id or default_event_id(conn)
    require_capability(conn, who, Capability.AGGREGATE, event_id=event_id)
    return assignment.progress(conn, event_id)


@router.post("/organizer/assignments/generate", summary="Top up judge assignments")
def post_generate(conn: Conn, who: Who, event_id: str | None = None) -> dict[str, Any]:
    event_id = event_id or default_event_id(conn)
    require_operation(conn, who, Operation.MANAGE_JUDGES, event_id=event_id)
    with transaction(conn):
        plan = assignment.generate_assignments(
            conn, event_id, actor_user_id=who.user_id, actor_role=who.role
        )
    return {
        "event_id": event_id,
        "created": plan.created,
        "skipped_duplicates": plan.skipped_duplicates,
        "unfillable": plan.unfillable,
        "per_judge": plan.per_judge,
    }


@router.get("/organizer/results", summary="Normalized leaderboard")
def get_results(
    conn: Conn,
    who: Who,
    event_id: str | None = None,
    method: str | None = Query(default=None, description="raw | shrunken_z | additive_ridge"),
) -> dict[str, Any]:
    event_id = event_id or default_event_id(conn)
    require_capability(conn, who, Capability.AGGREGATE, event_id=event_id)
    if method is not None and method not in normalize.METHODS:
        raise ApiError(
            "invalid_request",
            f"unknown normalization method '{method}'",
            extra={"methods": list(normalize.METHODS)},
        )
    result = results.get_results(conn, event_id, method=method)
    return {
        "event_id": event_id,
        "method": result.method,
        "observations": result.observations,
        "judge_spread_before": result.judge_spread_before,
        "judge_spread_after": result.judge_spread_after,
        "residual_sd": result.residual_sd,
        "pooled_mean": result.pooled_mean,
        "pooled_sd": result.pooled_sd,
        "iterations": result.iterations,
        "converged": result.converged,
        "params": result.params,
        "leaderboard": results.leaderboard(conn, event_id, method=method),
        "judges": [j.__dict__ for j in result.judges],
    }


@router.get(
    "/organizer/normalization-proof",
    summary="The normalization proof, as plain text",
    response_class=Response,
)
def get_normalization_proof(request: Request, conn: Conn, who: Who,
                            event_id: str | None = None) -> Response:
    """The written demonstration, served from the same code that ranks.

    The bonus challenge asks for an explanation and a demonstration on the
    fixture data. Serving it from the running portal rather than only shipping a
    static file means it cannot drift away from the implementation: if the
    solver changes, this document changes with it. The identical text is
    committed at docs/normalization-proof.txt for anyone reading the repository
    without booting it.
    """
    event_id = event_id or default_event_id(conn)
    require_capability(conn, who, Capability.AGGREGATE, event_id=event_id)
    settings = request.app.state.settings
    if settings.fixtures_path is None or not settings.fixtures_path.exists():
        raise ApiError("not_found", "fixtures.json is not available to this deployment")
    with settings.fixtures_path.open(encoding="utf-8") as handle:
        fixtures = json.load(handle)
    weights = results.rubric_weights(conn, event_id)
    return Response(
        content=normalize.build_proof(fixtures, weights=weights or None),
        media_type="text/plain; charset=utf-8",
    )


@router.get("/results", summary="Published results, once the organizer publishes them")
def public_results(conn: Conn, who: Who, event_id: str | None = None) -> dict[str, Any]:
    """The T3 rule: results are hidden from everyone but organizers during the
    voting window."""
    event_id = event_id or default_event_id(conn)
    event = get_event(conn, event_id)
    if not event["results_published"]:
        from ..security import deny, has_capability

        if not has_capability(who.role, Capability.AGGREGATE):
            raise deny(
                conn,
                who,
                "results_embargoed",
                detail="results for this event have not been published yet",
                event_id=event_id,
                target_type="event",
                target_id=event_id,
            )
    board = results.leaderboard(conn, event_id)
    return {
        "event_id": event_id,
        "published": bool(event["results_published"]),
        "leaderboard": [
            {
                "position": row["position"],
                "project_id": row["project_id"],
                "title": row["title"],
                "team": row["team"],
                "track": row["track"],
                "score": row["score"],
                "n_reviews": row["n_reviews"],
                "low_confidence": row["low_confidence"],
            }
            for row in board
        ],
    }


@router.get("/organizer/duplicates", summary="Detected duplicate submissions")
def get_duplicates(conn: Conn, who: Who, event_id: str | None = None) -> dict[str, Any]:
    event_id = event_id or default_event_id(conn)
    require_capability(conn, who, Capability.AGGREGATE, event_id=event_id)
    event = get_event(conn, event_id)
    report = seed.duplicate_report(conn, event_id)
    return {
        "event_id": event_id,
        "exclude_duplicates": bool(event["exclude_duplicates"]),
        "duplicates": report,
        "note": "Flagged projects are excluded from the ranking while "
        "exclude_duplicates is on. Their ballots always remain in the "
        "calibration data, because dropping an observation would bias the "
        "bias estimate of the judge who cast it.",
    }


@router.post("/organizer/duplicates/{project_id}", summary="Confirm or dismiss a duplicate flag")
def decide_duplicate(
    conn: Conn, who: Who, project_id: str, body: DuplicateDecision
) -> dict[str, Any]:
    project = query_one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
    if project is None:
        raise ApiError("not_found", f"no project '{project_id}'")
    event_id = project["event_id"]
    require_operation(conn, who, Operation.MANAGE_EVENT, event_id=event_id)

    with transaction(conn):
        if body.action == "dismiss":
            conn.execute(
                "UPDATE projects SET duplicate_of = NULL, duplicate_reason = NULL, "
                "status = CASE WHEN status = 'flagged_duplicate' THEN 'submitted' ELSE status END "
                "WHERE id = ?",
                (project_id,),
            )
        else:
            conn.execute(
                "UPDATE projects SET status = 'flagged_duplicate' WHERE id = ?", (project_id,)
            )
        results.invalidate(conn, event_id)
        audit.record(
            conn,
            f"duplicate.{body.action}ed",
            event_id=event_id,
            actor_user_id=who.user_id,
            actor_role=who.role,
            target_type="project",
            target_id=project_id,
            detail={"note": body.note, "was_duplicate_of": project["duplicate_of"]},
        )
    return {"project_id": project_id, "action": body.action}


# ------------------------------------------------------------------- audit ---


@router.get("/audit", summary="Read the audit log")
def get_audit(
    conn: Conn,
    who: Who,
    event_id: str | None = None,
    action: str | None = None,
    reason_code: str | None = None,
    actor: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    require_capability(conn, who, Capability.AUDIT_LOG, event_id=event_id)
    return {
        "entries": audit.list_entries(
            conn,
            event_id=event_id,
            action=action,
            reason_code=reason_code,
            actor_user_id=actor,
            limit=limit,
            offset=offset,
        ),
        "total": query_one(conn, "SELECT COUNT(*) AS n FROM audit_log")["n"],
    }


@router.get("/audit/verify", summary="Verify the audit hash chain")
def verify_audit(conn: Conn, who: Who) -> dict[str, Any]:
    """Recompute every hash in the chain.

    An append-only claim is only worth something if it can be checked, so the
    check is an endpoint rather than a paragraph in a document.
    """
    require_capability(conn, who, Capability.AUDIT_LOG)
    return audit.verify_chain(conn)


# ----------------------------------------------------------------- exports ---


@router.get("/exports/{stage}.csv", summary="CSV export, one per pipeline stage")
def export_csv(
    conn: Conn,
    who: Who,
    stage: str,
    event_id: str | None = None,
    method: str | None = None,
) -> Response:
    """Stages: projects, teams, judges, assignments, scores, results, audit."""
    if stage not in exports.EXPORTERS:
        raise ApiError(
            "not_found",
            f"no export stage '{stage}'",
            extra={"stages": sorted(exports.EXPORTERS)},
        )
    event_id = event_id or default_event_id(conn)
    capability = Capability.AUDIT_LOG if stage == "audit" else Capability.AGGREGATE
    require_capability(conn, who, capability, event_id=event_id)

    body = exports.render_stage(
        conn, stage, event_id,
        actor_user_id=who.user_id, actor_role=who.role, method=method,
    )
    return Response(
        content=body,
        # No BOM, and charset declared. The suite reads the first line and
        # looks for a comma in it; a BOM would sit in front of the header.
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stage}-{event_id}.csv"'},
    )


@router.get("/exports/event.json", summary="Whole-event snapshot")
def export_json(conn: Conn, who: Who, event_id: str | None = None) -> dict[str, Any]:
    event_id = event_id or default_event_id(conn)
    require_capability(conn, who, Capability.AGGREGATE, event_id=event_id)
    payload = exports.export_event_json(conn, event_id)
    audit.record(
        conn, "export.json", event_id=event_id, actor_user_id=who.user_id,
        actor_role=who.role, target_type="export", target_id="event.json",
    )
    return payload


@router.post("/imports/event.json", summary="Bulk import an event snapshot")
async def import_json(request: Request, conn: Conn, who: Who) -> dict[str, Any]:
    """Reads back what /api/exports/event.json writes, and also reads
    fixtures.json unchanged.

    Adoptability asks for a path out as well as in, and a path out you cannot
    reverse is not a migration, it is a download.
    """
    require_operation(conn, who, Operation.MANAGE_EVENT)
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise ApiError("invalid_request", "body is not valid JSON") from exc
    if not isinstance(payload, dict) or "event" not in payload:
        raise ApiError("invalid_request", "expected an object with an 'event' key")

    with transaction(conn):
        summary = seed.seed(conn, payload, dev_tokens=False)
        results.invalidate(conn, summary["event_id"])
        audit.record(
            conn, "import.event", event_id=summary["event_id"], actor_user_id=who.user_id,
            actor_role=who.role, target_type="event", target_id=summary["event_id"],
            detail={"counts": summary["counts"]},
        )
    return {"imported": summary["counts"], "event_id": summary["event_id"]}


# ------------------------------------------------------------ verification ---


@router.get("/judges/{judge_id}/record", summary="Signed judge participation record")
def judge_record_certificate(conn: Conn, who: Who, judge_id: str) -> dict[str, Any]:
    """A verifiable statement of what a judge actually did.

    Issued once and stored. Anyone can fetch the same JSON later at
    GET /api/records/{record_hash} and recompute the hash. No ballot scores
    are included.
    """
    judge = query_one(conn, "SELECT * FROM judges WHERE id = ?", (judge_id,))
    if judge is None:
        raise ApiError("not_found", f"no judge '{judge_id}'")
    event_id = judge["event_id"]
    if who.user_id != judge["user_id"]:
        require_capability(conn, who, Capability.AGGREGATE, event_id=event_id)

    completed = query_one(
        conn,
        "SELECT COUNT(*) AS n FROM scores WHERE event_id = ? AND judge_id = ?",
        (event_id, judge_id),
    )["n"]
    assigned = query_one(
        conn,
        "SELECT COUNT(*) AS n FROM assignments WHERE event_id = ? AND judge_id = ?",
        (event_id, judge_id),
    )["n"]
    tracks = [
        r["track_id"]
        for r in query(conn, "SELECT track_id FROM judge_tracks WHERE judge_id = ?", (judge_id,))
    ]
    event = get_event(conn, event_id)
    with transaction(conn):
        return records.issue(
            conn,
            kind="judge",
            subject_id=judge_id,
            event_id=event_id,
            body={
                "judge_id": judge_id,
                "name": judge["display_name"],
                "event": {"id": event_id, "name": event["name"]},
                "tracks": sorted(tracks),
                "reviews_completed": int(completed),
                "reviews_assigned": int(assigned),
            },
        )


@router.get("/records/{record_hash}", summary="Fetch a public hash-anchored record")
def public_record(conn: Conn, record_hash: str) -> dict[str, Any]:
    payload = records.get_by_hash(conn, record_hash)
    if payload is None:
        raise ApiError("not_found", f"no record '{record_hash}'")
    return payload


@router.post("/records/verify", summary="Recompute a record hash")
async def verify_record(conn: Conn, request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise ApiError("invalid_request", "body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ApiError("invalid_request", "expected an object")
    return records.verify_payload(conn, payload)


@router.get("/projects/{project_id}/certificate", summary="Published project certificate")
def project_certificate(conn: Conn, who: Who, project_id: str) -> dict[str, Any]:
    project = query_one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
    if project is None or project["status"] == "draft":
        raise ApiError("not_found", f"no project '{project_id}'")
    event = get_event(conn, project["event_id"])
    if not event["results_published"] and not has_capability(who.role, Capability.AGGREGATE):
        raise ApiError("results_embargoed", "certificates are issued after results are published")
    board = results.leaderboard(conn, project["event_id"])
    row = next((item for item in board if item["project_id"] == project_id), None)
    if row is None:
        raise ApiError("not_found", "project is not on the published ranking")
    with transaction(conn):
        return records.issue(
            conn,
            kind="certificate",
            subject_id=project_id,
            event_id=project["event_id"],
            body={
                "project_id": project_id,
                "title": row["title"],
                "team": row["team"],
                "track": row["track"],
                "event": {"id": event["id"], "name": event["name"]},
                "position": row["position"],
                "method": results.get_results(conn, project["event_id"]).method,
                "n_reviews": row["n_reviews"],
            },
        )
