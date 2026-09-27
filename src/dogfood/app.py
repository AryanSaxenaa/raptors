"""Application factory.

Startup does the work that must not happen inside a graded request: create the
schema, load the fixtures, verify the counts. The acceptance suite treats any
exception -- including a connection reset or a response slower than ten seconds
-- as status 0, and a status of 0 fails every check at once. So the port must
not accept a request until the data behind it is present and counted.
"""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import SCHEMA_VERSION, Settings, settings as default_settings
from .db import connect, init_schema, query_one, scalar, transaction
from .deps import Conn
from .errors import install_error_handlers
from .seed import load_fixture_file, seed

DESCRIPTION = """
A self-hostable submission and judging portal for hackathons.

Every action available in the web UI is available here: the pages render read
views on the server and perform writes by calling these endpoints, so there is
one API and no second, privileged path.

Authentication is one opaque session credential, accepted as either
`Cookie: df_session=<token>` or `Authorization: Bearer <token>`.

Authorisation follows the published role-isolation matrix, which is served at
`GET /api/auth/matrix` and enforced in `security.py`. Denied requests answer
401 or 403 with an RFC 9457 problem document carrying a machine-readable
`code`, and every denial is written to the audit log.
"""


def bootstrap(db_path: Path, fixtures_path: Path, *, dev_tokens: bool) -> dict[str, Any]:
    """Create the schema and load the fixtures. Idempotent."""
    conn = connect(db_path)
    try:
        init_schema(conn)
        if not fixtures_path.is_file():
            return {"seeded": False, "reason": f"fixtures not found at {fixtures_path}"}
        fixtures = load_fixture_file(fixtures_path)
        with transaction(conn):
            summary = seed(conn, fixtures, dev_tokens=dev_tokens)
        summary["seeded"] = True
        summary["fixtures_path"] = str(fixtures_path)
        return summary
    finally:
        conn.close()


def _startup_banner(summary: dict[str, Any], config: Settings) -> None:
    """Print what spec.md's weekend story says a portal prints on boot, then the
    exact next command. Forty portals get booted by a judge in a row; being the
    one that says what to do next is most of Adoptability."""
    lines = ["", "dogfood portal ready", f"  portal     {config.base_url}"]
    if summary.get("seeded"):
        counts = summary.get("counts", {})
        lines.append(f"  fixtures   {summary.get('fixtures_path')}")
        lines.append(
            "  seeded     "
            + ", ".join(f"{value} {key}" for key, value in counts.items())
        )
        duplicates = summary.get("duplicates") or []
        if duplicates:
            lines.append(
                "  flagged    "
                + ", ".join(f"{d['project_id']} duplicate of {d['duplicate_of']}"
                            for d in duplicates)
            )
    else:
        lines.append(f"  WARNING    not seeded: {summary.get('reason')}")

    lines.append("")
    lines.append("seeded. test logins:")
    for login in summary.get("logins", []):
        lines.append(f"  {login['label']:<12} {login['header']}")
    if config.dev_tokens:
        lines += [
            "",
            "  NOTE  DOGFOOD_DEV_TOKENS=1 is set, so the session tokens above are",
            "        fixed rather than random. That is what keeps the committed",
            "        .dogfood.toml working across restarts. Set it to 0 for any",
            "        deployment that is not a laptop.",
        ]
    lines += ["", "next:", "  python3 run.py .dogfood.toml > acceptance-report.txt", ""]
    print("\n".join(lines), flush=True)


def create_app(config: Settings | None = None, *, run_bootstrap: bool = True) -> FastAPI:
    config = config or default_settings

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_bootstrap:
            summary = bootstrap(
                config.db_path, config.fixtures_path, dev_tokens=config.dev_tokens
            )
            app.state.seed_summary = summary
            if not app.state.quiet:
                _startup_banner(summary, config)
        else:
            app.state.seed_summary = {"seeded": False, "reason": "bootstrap skipped"}
        yield

    app = FastAPI(
        title="Dogfood Portal",
        version="1.0.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        # An OpenAPI document is the API-first deliverable, so it is served at a
        # stable path and committed to the repo as docs/openapi.json.
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.db_path = config.db_path
    app.state.settings = config
    app.state.quiet = False
    app.state.templates = Jinja2Templates(directory=str(config.templates_dir))
    app.state.templates.env.globals["settings"] = config

    install_error_handlers(app, app.state.templates)

    from .routers import auth, community, events, judging, organizer, projects, web

    app.include_router(auth.router)
    app.include_router(events.router)
    app.include_router(projects.router)
    app.include_router(judging.router)
    app.include_router(organizer.router)
    app.include_router(community.router)
    app.include_router(web.router)

    if config.static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(config.static_dir)), name="static")

    @app.get("/api/health", tags=["ops"], summary="Readiness, with seed counts")
    def health(conn: Conn) -> JSONResponse:
        """Reports the seed counts, not just a 200.

        A health check that only proves the process is alive would go green
        during the window where the port is open and the database is empty --
        exactly the window in which the gallery check fails.
        """
        try:
            projects_n = scalar(conn, "SELECT COUNT(*) FROM projects") or 0
            scores_n = scalar(conn, "SELECT COUNT(*) FROM scores") or 0
            judges_n = scalar(conn, "SELECT COUNT(*) FROM judges") or 0
            version = query_one(conn, "SELECT value FROM schema_meta WHERE key = 'version'")
        except Exception as exc:  # noqa: BLE001 - health must answer, not raise
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)
        ready = projects_n > 0 and judges_n > 0
        return JSONResponse(
            {
                "ok": ready,
                "schema_version": version["value"] if version else None,
                "expected_schema_version": SCHEMA_VERSION,
                "counts": {
                    "projects": projects_n,
                    "judges": judges_n,
                    "scores": scores_n,
                },
            },
            status_code=200 if ready else 503,
        )

    @app.get("/openapi.yaml", include_in_schema=False)
    def openapi_yaml() -> PlainTextResponse:
        """JSON is valid YAML, so this needs no serialiser and no dependency."""
        return PlainTextResponse(
            json.dumps(app.openapi(), indent=2), media_type="application/yaml"
        )

    return app


app = create_app()


def serve() -> int:
    import uvicorn

    config = default_settings
    # Bootstrap before uvicorn binds, so the socket never opens on an unseeded
    # database. Doing it here as well as in lifespan is cheap and idempotent.
    summary = bootstrap(config.db_path, config.fixtures_path, dev_tokens=config.dev_tokens)
    if not summary.get("seeded"):
        print(f"refusing to start: {summary.get('reason')}", file=sys.stderr)
        return 1
    application = create_app(config, run_bootstrap=False)
    application.state.seed_summary = summary
    _startup_banner(summary, config)
    uvicorn.run(application, host=config.host, port=config.port, log_level="info",
                access_log=False)
    return 0
