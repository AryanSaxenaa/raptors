"""One error shape for the whole surface.

Every failure carries a machine-readable `code`. The codes are the contract the
tests assert on: a 403 from the deadline guard must say `submissions_closed`,
not merely be a 403, otherwise a CSRF rejection or a validation error would be
indistinguishable from real deadline enforcement.

Wire format is RFC 9457 problem details, plus `code`.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_MEDIA_TYPE = "application/problem+json"

# Every deny path in the codebase uses one of these. Kept in one place so the
# audit log, the tests and the HTTP body cannot drift apart.
CODES = {
    "not_authenticated": (401, "Not authenticated"),
    "role_required": (403, "Role not permitted"),
    "capability_required": (403, "Capability not permitted"),
    "peer_scores_denied": (403, "Another judge's scores are not visible to you"),
    "track_not_visible": (403, "Project is outside your assigned tracks"),
    "aggregate_denied": (403, "Aggregate results are not visible to you"),
    "audit_denied": (403, "Audit log is not visible to you"),
    "results_embargoed": (403, "Results are hidden until the organizer publishes them"),
    "submissions_closed": (403, "Submissions are closed for this event"),
    "voting_closed": (403, "Voting is closed for this event"),
    "not_team_member": (403, "You are not a member of this team"),
    "not_assigned": (403, "You are not assigned to this project"),
    "rate_limited": (429, "Too many requests"),
    "not_found": (404, "Not found"),
    "conflict": (409, "Conflict"),
    "invalid_request": (400, "Invalid request"),
    "unknown_criterion": (400, "Unknown rubric criterion"),
    "origin_rejected": (403, "Cross-origin write rejected"),
}


class ApiError(Exception):
    """A deliberate, coded failure. The only exception type handlers raise."""

    def __init__(
        self,
        code: str,
        detail: str | None = None,
        *,
        status: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        known_status, title = CODES.get(code, (400, "Invalid request"))
        self.code = code
        self.status = status or known_status
        self.title = title
        self.detail = detail or title
        self.extra = extra or {}
        super().__init__(f"{code}: {self.detail}")

    def to_problem(self, instance: str | None = None) -> dict[str, Any]:
        problem: dict[str, Any] = {
            "type": f"https://dogfood.local/errors/{self.code}",
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "code": self.code,
        }
        if instance:
            problem["instance"] = instance
        problem.update(self.extra)
        return problem


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


def install_error_handlers(app: Any, templates: Any) -> None:
    """Register the three handlers that cover every failure path."""

    def _render(request: Request, problem: dict[str, Any]) -> Any:
        if _wants_html(request):
            return templates.TemplateResponse(
                request,
                "error.html",
                {"problem": problem},
                status_code=problem["status"],
            )
        return JSONResponse(problem, status_code=problem["status"], media_type=PROBLEM_MEDIA_TYPE)

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> Any:
        return _render(request, exc.to_problem(str(request.url.path)))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> Any:
        code = {401: "not_authenticated", 403: "role_required", 404: "not_found"}.get(
            exc.status_code, "invalid_request"
        )
        problem = ApiError(code, str(exc.detail), status=exc.status_code).to_problem(
            str(request.url.path)
        )
        return _render(request, problem)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> Any:
        # 422 rather than 400 so that a malformed body is never mistaken for a
        # deliberate refusal. The deadline guard runs before validation, so a
        # closed event always answers `submissions_closed` instead of this.
        problem = ApiError(
            "invalid_request",
            "Request body failed validation",
            status=422,
            extra={"errors": _safe_errors(exc)},
        ).to_problem(str(request.url.path))
        return _render(request, problem)


def _safe_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    out = []
    for err in exc.errors():
        out.append(
            {
                "loc": [str(part) for part in err.get("loc", [])],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
        )
    return out
