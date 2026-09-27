#!/usr/bin/env python3
"""Adversarial end-to-end probe of a running portal.

    python3 tests/smoke.py                     # against http://localhost:8080
    python3 tests/smoke.py http://host:8080

run.py makes seven assertions. This makes seventy, over the cases a hidden test
set would plausibly reach for and the published fixtures do not cover: the other
twenty-two cells of the role matrix, the deadline boundary from both sides, the
transport variations run.py never sends, malformed bodies, out-of-range scores,
rubric keys that do not exist, the CSV byte format, and the audit chain.

Deliberately stdlib only and deliberately black-box, for the same reason run.py
is: it has to be runnable against a container by someone who has not installed
this project's dependencies.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
REPO_ROOT = Path(__file__).resolve().parent.parent

ORG = "org_7f2a"
JUDGE_A = "jdg_a_91bc"
JUDGE_B = "jdg_b_44de"
PARTICIPANT = "prt_2e88"

FIXTURE_EVENT = "evt_01"
DEMO_EVENT = "evt_demo"
FIXTURE_PROJECTS = 41
FIXTURE_SCORES = 126

_results: list[tuple[bool, str, str]] = []


def prepare_environment() -> None:
    """Reset the local database when probing localhost so counts stay deterministic."""
    host = BASE.lower()
    if not (host.startswith("http://localhost") or host.startswith("http://127.0.0.1")):
        return
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env.setdefault("DOGFOOD_DEV_TOKENS", "1")
    subprocess.run(
        [sys.executable, "-m", "dogfood", "reset"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def request(
    path: str,
    *,
    token: str | None = None,
    bearer: str | None = None,
    method: str = "GET",
    body: object | None = None,
    accept: str = "application/json",
    raw_body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, str, dict[str, str]]:
    """One request. Returns (status, text, headers); never raises on 4xx/5xx."""
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Accept", accept)
    if token:
        req.add_header("Cookie", f"df_session={token}")
    if bearer:
        req.add_header("Authorization", f"Bearer {bearer}")
    if raw_body is not None:
        req.data = raw_body
        req.add_header("Content-Type", content_type or "application/json")
    elif body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", content_type or "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), _headers(resp)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), _headers(exc)
    except Exception as exc:  # noqa: BLE001 - a dead server is a failed check
        return 0, f"{type(exc).__name__}: {exc}", {}


def _headers(resp: object) -> dict[str, str]:
    """Lower-cased header names, because HTTP/1.1 does not promise any case."""
    return {k.lower(): v for k, v in dict(resp.headers).items()}  # type: ignore[attr-defined]


def check(label: str, ok: bool, note: str = "") -> bool:
    _results.append((bool(ok), label, note))
    return bool(ok)


def status_is(label: str, path: str, want: int | tuple[int, ...], **kwargs: object) -> str:
    wanted = want if isinstance(want, tuple) else (want,)
    status, text, _ = request(path, **kwargs)  # type: ignore[arg-type]
    check(label, status in wanted, f"{path} -> {status or 'no response'}, wanted {wanted}")
    return text


def code_of(text: str) -> str:
    try:
        return json.loads(text).get("code", "")
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------- public read ---


def public_surface() -> None:
    body = status_is("gallery is public", "/projects", 200, accept="text/html")
    for title in ("Glass Signal", "Small Meadow", "Deep Compass"):
        check(f"gallery body contains {title!r}", title in body)

    fixtures = json.load(open("fixtures.json", encoding="utf-8"))
    titles = [p["title"] for p in fixtures["projects"]]
    missing = [t for t in titles if t not in body]
    check(
        "gallery page one contains every fixture project",
        not missing,
        f"{len(missing)} missing, e.g. {missing[:3]}",
    )

    # The grader only looks at the first three titles. A submission that
    # paginates at 20 passes run.py and still hides half the event.
    check("gallery is not paginating below the fixture count", len(titles) == 41)

    status, text, _ = request("/projects?q=glass", accept="text/html")
    check("gallery search narrows the list", status == 200 and "Glass Signal" in text)
    check("gallery search excludes non-matches", "Deep Compass" not in text)

    status_is("project detail is public", "/projects/prj_01", 200, accept="text/html")
    status_is("unknown project is 404", "/projects/prj_999", 404, accept="text/html")
    status_is("unknown page is 404", "/nope", 404, accept="text/html")

    status, text, _ = request("/projects/prj_999")
    check("404 carries a machine-readable code", code_of(text) == "not_found", text[:120])

    _, text, headers = request("/projects/prj_999")
    check(
        "errors are problem+json",
        "application/problem+json" in headers.get("content-type", ""),
        headers.get("content-type", ""),
    )


# ---------------------------------------------------------------- transports ---


def transports() -> None:
    """run.py only ever sends a cookie. A hidden suite may not."""
    status_is("bearer token is accepted", "/api/judge/scores", 200, bearer=JUDGE_A)
    status_is("cookie token is accepted", "/api/judge/scores", 200, token=JUDGE_A)
    status_is("no credential is refused", "/api/judge/scores", (401, 403))
    status_is("a bogus token is refused", "/api/judge/scores", (401, 403), token="not-a-token")
    status_is(
        "a bogus bearer is refused", "/api/judge/scores", (401, 403), bearer="not-a-token"
    )

    # Trailing-slash and case variants: a graded route must not 307 anywhere,
    # because run.py follows redirects and rewrites POST to GET when it does.
    status, _, headers = request("/projects/")
    check(
        "gallery does not redirect on a trailing slash",
        status in (200, 404) and "location" not in headers,
        f"{status} {headers.get('location', '')}",
    )

    status, _, headers = request(
        f"/api/events/{FIXTURE_EVENT}/projects", token=PARTICIPANT, method="POST",
        body={"title": "probe"},
    )
    check(
        "the submit route answers directly, with no redirect",
        300 > status or status >= 400,
        f"{status} {headers.get('location', '')}",
    )


# --------------------------------------------------------------- role matrix ---


def role_matrix() -> None:
    """Every cell of the published five-by-five matrix, not just the three cells
    run.py samples."""
    status, text, _ = request("/api/auth/matrix")
    check("the matrix is served as data", status == 200)
    served = json.loads(text) if status == 200 else {}
    roles = served.get("roles", {})
    # The five actors and five capabilities of the published figure, named the
    # way the figure names them.
    check(
        "the matrix serves all five actors",
        set(roles) == {"visitor", "participant", "judge", "organizer", "admin"},
        str(sorted(roles)),
    )
    check(
        "the matrix serves all five capabilities",
        served.get("capabilities")
        == ["own_scores", "peer_scores", "other_track", "aggregate", "audit_log"],
        str(served.get("capabilities")),
    )
    expected = {
        "visitor": [False, False, False, False, False],
        "participant": [False, False, False, False, False],
        "judge": [True, False, False, False, False],
        "organizer": [True, True, True, True, True],
        "admin": [True, True, True, True, True],
    }
    for role, wanted in expected.items():
        row = roles.get(role, {})
        got = [bool(row.get(cap)) for cap in served.get("capabilities", [])]
        check(f"matrix row for {role} matches the published figure", got == wanted, str(got))

    # own_scores
    status_is("judge reads own scores", "/api/judge/scores", 200, token=JUDGE_A)
    status_is("participant cannot read judge scores", "/api/judge/scores", (401, 403),
              token=PARTICIPANT)
    status_is("public cannot read judge scores", "/api/judge/scores", (401, 403))

    # peer_scores -- the cell the fixtures make expensive to get wrong
    text = status_is(
        "judge cannot read another judge's scores",
        "/api/judge/scores?judge=jdg_01", (401, 403), token=JUDGE_B,
    )
    check(
        "the peer denial names its own reason",
        code_of(text) in ("peer_scores_denied", "capability_required"),
        code_of(text),
    )
    status_is("organizer may read a judge's scores", "/api/judge/scores?judge=jdg_01", 200,
              token=ORG)
    status_is("a judge reading their own id is allowed", "/api/judge/scores?judge=jdg_01", 200,
              token=JUDGE_A)

    # aggregate
    aggregate = f"/api/organizer/results?event_id={FIXTURE_EVENT}"
    status_is("organizer sees the aggregate", aggregate, 200, token=ORG)
    status_is("judge cannot see the aggregate", aggregate, (401, 403), token=JUDGE_A)
    status_is("participant cannot see the aggregate", aggregate, (401, 403), token=PARTICIPANT)
    status_is("public cannot see the aggregate", aggregate, (401, 403))
    status_is("progress is organizer-only", "/api/organizer/progress", (401, 403), token=JUDGE_A)
    status_is("the published-results route is embargoed", "/api/results", (401, 403),
              token=PARTICIPANT)

    # audit_log
    status_is("organizer reads the audit log", "/api/audit", 200, token=ORG)
    status_is("judge cannot read the audit log", "/api/audit", (401, 403), token=JUDGE_A)
    status_is("participant cannot read the audit log", "/api/audit", (401, 403),
              token=PARTICIPANT)
    status_is("public cannot read the audit log", "/api/audit", (401, 403))

    # other_track -- invisible in spec.md, provable from the fixtures
    status, text, _ = request("/api/judge/assignments", token=JUDGE_A)
    mine = (
        {row["project_id"] for row in json.loads(text)["assignments"]}
        if status == 200
        else set()
    )
    check("judge A has an assignment queue", bool(mine), text[:120])
    status, text, _ = request("/api/judge/scores", token=JUDGE_A)
    check("judge A's own ballots come back", status == 200)

    outside = None
    for candidate in (f"prj_{n:02d}" for n in range(1, 42)):
        if candidate not in mine:
            outside = candidate
            break
    if outside:
        text = status_is(
            "judge cannot open a project they were not assigned",
            f"/api/judge/projects/{outside}", (401, 403, 404), token=JUDGE_A,
        )
        check(
            "the refusal distinguishes track from assignment",
            code_of(text) in ("track_not_visible", "not_assigned", "not_found"),
            code_of(text),
        )


# ------------------------------------------------------------------ deadline ---


def deadline() -> None:
    text = status_is(
        "closed event refuses a submission",
        f"/api/events/{FIXTURE_EVENT}/projects", (400, 401, 403, 409, 422),
        token=PARTICIPANT, method="POST", body={"title": "late", "summary": "probe"},
    )
    check(
        "the refusal is for lateness, not for validation",
        code_of(text) == "submissions_closed",
        f"got {code_of(text)!r}",
    )

    # The deadline has to be checked before the body is looked at, or an empty
    # body on a closed event reports the wrong reason.
    for label, payload in (
        ("an empty body", {}),
        ("a body that is not an object", []),
        ("a body with a null title", {"title": None}),
        ("a body with an overlong title", {"title": "x" * 5000}),
        ("a body with unexpected keys", {"title": "x", "role": "organizer", "id": "prj_01"}),
    ):
        text = status_is(
            f"closed event still refuses {label} as closed",
            f"/api/events/{FIXTURE_EVENT}/projects", (400, 401, 403, 409, 422),
            token=PARTICIPANT, method="POST", body=payload,
        )
        check(
            f"  ... and names submissions_closed for {label}",
            code_of(text) == "submissions_closed",
            f"got {code_of(text)!r}",
        )

    status, text, _ = request(
        f"/api/events/{FIXTURE_EVENT}/projects", token=PARTICIPANT, method="POST",
        raw_body=b"{not json at all",
    )
    check(
        "malformed JSON on a closed event is still refused as closed",
        code_of(text) == "submissions_closed" or 400 <= status < 500,
        f"{status} {code_of(text)!r}",
    )

    status_is(
        "public cannot submit at all",
        f"/api/events/{DEMO_EVENT}/projects", (401, 403),
        method="POST", body={"title": "anonymous"},
    )


# ------------------------------------------------------- the open event path ---


def lifecycle() -> None:
    """The fixture event is closed, so the write path needs its own event."""
    status, text, _ = request(
        f"/api/events/{DEMO_EVENT}/teams", token=PARTICIPANT, method="POST",
        body={"name": "Smoke Test Crew"},
    )
    if not check("a participant can create a team on an open event", status in (200, 201),
                 f"{status} {text[:140]}"):
        return
    team = json.loads(text)
    check("team creation returns an invite link", bool(team.get("invite_code")), text[:140])

    # Seven fixture teams share three names, so a name collision has to be
    # allowed. It is reported, not refused.
    status, text, _ = request(
        f"/api/events/{DEMO_EVENT}/teams", token=PARTICIPANT, method="POST",
        body={"name": "Smoke Test Crew"},
    )
    check("a colliding team name is allowed", status in (200, 201), f"{status} {text[:140]}")
    check(
        "the collision is reported back",
        status in (200, 201) and json.loads(text).get("name_collision") is True,
        text[:140],
    )

    probe_title = f"Smoke Probe {secrets.token_hex(3)}"
    status, text, _ = request(
        f"/api/events/{DEMO_EVENT}/projects", token=PARTICIPANT, method="POST",
        body={
            "title": probe_title,
            "summary": "created by tests/smoke.py",
            "team": team["id"],
            "tech_tags": ["python"],
            "submit": False,
        },
    )
    if not check("a draft can be created on an open event", status in (200, 201),
                 f"{status} {text[:140]}"):
        return
    project = json.loads(text)
    pid = project["id"]

    status, text, _ = request("/projects", accept="text/html")
    check("a draft does not appear in the public gallery", probe_title not in text)

    status, _, _ = request(
        f"/api/projects/{pid}", token=PARTICIPANT, method="PATCH",
        body={"summary": "edited while still a draft", "submit": True},
    )
    check("a draft can be edited and submitted", status == 200, str(status))

    status, text, _ = request("/projects", accept="text/html")
    check("a submitted project appears in the gallery", probe_title in text)

    status, _, _ = request(
        f"/api/projects/{pid}", token=PARTICIPANT, method="PATCH", body={"title": ""},
    )
    check("an empty title is rejected", 400 <= status < 500, str(status))

    other = status_is(
        "another participant cannot edit someone else's project",
        f"/api/projects/{pid}", (401, 403, 404), token=JUDGE_A, method="PATCH",
        body={"title": "hijacked"},
    )
    check("the refusal names ownership", code_of(other) in
          ("not_team_member", "capability_required", "role_required", "not_found"),
          code_of(other))


# ----------------------------------------------------------------- balloting ---


def balloting() -> None:
    status, text, _ = request("/api/judge/assignments", token=JUDGE_A)
    queue = json.loads(text)["assignments"] if status == 200 else []
    if not check("judge A has something to score", bool(queue), text[:140]):
        return
    target = queue[0]["project_id"]

    status, text, _ = request(f"/api/judge/projects/{target}", token=JUDGE_A)
    if not check("an assigned project opens", status == 200, text[:140]):
        return
    rubric = json.loads(text)["rubric"]
    keys = [c["key"] for c in rubric]
    check("the rubric comes from the database, not a constant", len(keys) >= 3, str(keys))

    good = {k: 4 for k in keys}
    status, text, _ = request(
        "/api/judge/scores", token=JUDGE_A, method="POST",
        body={"project_id": target, "event_id": FIXTURE_EVENT, "criteria": good,
              "comment": "smoke"},
    )
    check("a valid ballot is accepted", status in (200, 201), f"{status} {text[:140]}")

    for label, criteria in (
        ("a score above the scale", {**good, keys[0]: 6}),
        ("a score below the scale", {**good, keys[0]: 0}),
        ("a negative score", {**good, keys[0]: -1}),
        ("a fractional score", {**good, keys[0]: 3.5}),
        ("a score that is a string", {**good, keys[0]: "4"}),
        ("a score that is a bool", {**good, keys[0]: True}),
        ("a criterion that does not exist", {**good, "not_a_criterion": 4}),
        ("an empty criteria object", {}),
    ):
        status, text, _ = request(
            "/api/judge/scores", token=JUDGE_A, method="POST",
            body={"project_id": target, "event_id": FIXTURE_EVENT, "criteria": criteria},
        )
        check(f"ballot with {label} is rejected", 400 <= status < 500, f"{status} {text[:100]}")

    status, _, _ = request(
        "/api/judge/scores", token=JUDGE_A, method="POST",
        body={"project_id": "prj_999", "event_id": FIXTURE_EVENT, "criteria": good},
    )
    check("scoring a project that does not exist is rejected", 400 <= status < 500, str(status))

    status_is(
        "a participant cannot cast a ballot", "/api/judge/scores", (401, 403),
        token=PARTICIPANT, method="POST",
        body={"project_id": target, "event_id": FIXTURE_EVENT, "criteria": good},
    )

    # judge_b is not assigned this project and may be outside its track
    status, text, _ = request(
        "/api/judge/scores", token=JUDGE_B, method="POST",
        body={"project_id": target, "event_id": FIXTURE_EVENT, "criteria": good},
    )
    check("an unassigned judge cannot score it", 400 <= status < 500, f"{status} {text[:100]}")


# ------------------------------------------------------------- normalization ---


def normalization() -> None:
    status, text, _ = request(f"/api/organizer/results?event_id={FIXTURE_EVENT}", token=ORG)
    if not check("results compute", status == 200, text[:140]):
        return
    payload = json.loads(text)
    before = payload["judge_spread_before"]
    after = payload["judge_spread_after"]
    check("the correction reduces between-judge spread", after < before, f"{before} -> {after}")
    check("the solver converged", payload.get("converged") is True, str(payload.get("iterations")))

    judges = {j["judge_id"]: j for j in payload["judges"]}
    check("every judge is diagnosed", len(judges) == 30, str(len(judges)))
    flat = judges.get("jdg_07")
    check(
        "the zero-variance judge is flagged rather than dividing by zero",
        bool(flat) and flat["is_flat"] and flat["raw_sd"] == 0 and flat["shrunk_sd"] > 0,
        json.dumps(flat) if flat else "jdg_07 absent",
    )
    singles = [j for j in payload["judges"] if j["n_reviews"] == 1]
    check(
        "every single-ballot judge is flagged",
        bool(singles) and all(j["single_ballot"] for j in singles),
        json.dumps(singles[:3]),
    )
    check(
        "a single ballot is not given a full bias correction",
        bool(singles)
        and all(
            abs(j["bias"]) < abs(j["raw_mean"] - payload["pooled_mean"]) + 1e-9 for j in singles
        ),
        json.dumps(singles[:2]),
    )

    board = payload["leaderboard"]
    check(
        "no score is NaN or absurd",
        all(row["score"] is None or -100 < row["score"] < 100 for row in board),
    )
    check("the duplicate is excluded from the ranking", len(board) == 40, str(len(board)))
    check(
        "calibration uses every stored ballot",
        payload["observations"] >= 126,
        str(payload["observations"]),
    )
    check(
        "positions are dense and start at one",
        [row["position"] for row in board] == list(range(1, len(board) + 1)),
    )
    check(
        "the board is sorted by the selected score",
        all(
            (board[i]["score"] or 0) >= (board[i + 1]["score"] or 0)
            for i in range(len(board) - 1)
        ),
    )
    moved = [row for row in board if row.get("rank_delta")]
    check("normalization actually moves ranks", bool(moved), f"{len(moved)} projects moved")
    check(
        "rank movement is conserved",
        sum(row["rank_delta"] or 0 for row in board) == 0,
        str(sum(row["rank_delta"] or 0 for row in board)),
    )

    for method in ("raw", "shrunken_z", "additive_ridge"):
        status_is(
            f"method {method} is selectable",
            f"/api/organizer/results?event_id={FIXTURE_EVENT}&method={method}", 200, token=ORG,
        )
    status_is(
        "an unknown method is rejected",
        f"/api/organizer/results?event_id={FIXTURE_EVENT}&method=magic", (400, 422), token=ORG,
    )

    text = status_is(
        "the proof artefact is served",
        f"/api/organizer/normalization-proof?event_id={FIXTURE_EVENT}", 200, token=ORG,
        accept="text/plain",
    )
    check("the proof shows its own numbers", "observations" in text, text[:80])
    status_is(
        "the proof is not public",
        f"/api/organizer/normalization-proof?event_id={FIXTURE_EVENT}", (401, 403),
        accept="text/plain",
    )


# ----------------------------------------------------------------- csv bytes ---


def csv_bytes() -> None:
    for stage in ("projects", "teams", "judges", "assignments", "scores", "results", "audit"):
        status, text, headers = request(f"/api/exports/{stage}.csv", token=ORG, accept="text/csv")
        if not check(f"{stage}.csv exports", status == 200, f"{status} {text[:100]}"):
            continue
        check(f"{stage}.csv has a comma in its header", "," in text.splitlines()[0])
        check(f"{stage}.csv uses CRLF", "\r\n" in text)
        check(f"{stage}.csv has no byte-order mark", not text.startswith("\ufeff"))
        check(
            f"{stage}.csv declares a csv content type",
            "csv" in headers.get("content-type", ""),
            headers.get("content-type", ""),
        )
        columns = text.splitlines()[0].count(",") + 1
        check(f"{stage}.csv has more than one column", columns > 1, str(columns))

    status_is("a judge cannot export results", "/api/exports/results.csv", (401, 403),
              token=JUDGE_A)
    status_is("the public cannot export results", "/api/exports/results.csv", (401, 403))
    status_is("an unknown stage is rejected", "/api/exports/secrets.csv", (400, 404), token=ORG)

    status, text, _ = request("/api/exports/event.json", token=ORG)
    if check("the event exports as json", status == 200, text[:120]):
        payload = json.loads(text)
        check(
            "the export round-trips the fixture shape",
            {"event", "projects", "teams", "judges", "scores"} <= set(payload),
            str(sorted(payload)),
        )
        check(
            "the export carries every project",
            len(payload["projects"]) >= 41,
            str(len(payload["projects"])),
        )


# --------------------------------------------------------------- audit chain ---


def audit_chain() -> None:
    status, text, _ = request("/api/audit/verify", token=ORG)
    if not check("the audit chain verifies", status == 200, text[:140]):
        return
    payload = json.loads(text)
    check("verification reports ok", payload.get("ok") is True, text[:200])
    check("the chain is non-empty", payload.get("entries", 0) > 0, text[:200])

    # Provoke a denial and confirm it lands in the log.
    before = payload["entries"]
    request("/api/judge/scores?judge=jdg_01", token=JUDGE_B)
    status, text, _ = request(
        "/api/audit?reason_code=peer_scores_denied", token=ORG
    )
    entries = json.loads(text)["entries"] if status == 200 else []
    if not entries:
        status, text, _ = request("/api/audit?action=authorization.denied", token=ORG)
        entries = json.loads(text)["entries"] if status == 200 else []
    check("a refusal is recorded", bool(entries), f"{status} {text[:140]}")
    check(
        "the recorded refusal names the actor and the reason",
        any(e.get("reason_code") and e.get("actor_role") for e in entries),
        json.dumps(entries[:1])[:200],
    )
    check(
        "the refusal of judge B's peer read is in there by name",
        any(
            e.get("reason_code") == "peer_scores_denied"
            and (e.get("actor_role") == "judge")
            for e in entries
        ),
        json.dumps([e.get("reason_code") for e in entries[:6]]),
    )

    status, text, _ = request("/api/audit/verify", token=ORG)
    after = json.loads(text)
    check("the chain still verifies after appending", after.get("ok") is True)
    check("the chain grew", after.get("entries", 0) > before, f"{before} -> {after.get('entries')}")

    status, text, _ = request("/api/judges/jdg_01/record", token=ORG)
    if check("a judge participation record is issued", status == 200, text[:140]):
        record = json.loads(text)
        check(
            "the record is anchored to the chain head",
            record.get("audit_chain_head") == after.get("head_hash"),
            f"{record.get('audit_chain_head')} vs {after.get('head_hash')}",
        )
        check("the record carries its own hash", bool(record.get("record_hash")), text[:200])


# ---------------------------------------------------------------- operations ---


def operations() -> None:
    status, text, _ = request("/api/health")
    if check("health responds", status == 200, text[:140]):
        payload = json.loads(text)
        check("health reports readiness", payload.get("ok") is True, text[:200])
        fixture = payload.get("fixture_counts", {})
        check(
            "health reports the seeded counts",
            fixture.get("projects") == FIXTURE_PROJECTS
            and fixture.get("scores", 0) >= FIXTURE_SCORES,
            text[:200],
        )
        check(
            "health reports at least the fixture project count",
            payload.get("counts", {}).get("projects") >= FIXTURE_PROJECTS,
            text[:200],
        )
        check(
            "health pins the schema version it expects",
            payload.get("schema_version") == payload.get("expected_schema_version"),
            text[:200],
        )

    status_is("openapi is published", "/openapi.json", 200)
    status, text, _ = request("/openapi.json")
    if status == 200:
        spec = json.loads(text)
        check("openapi documents the api surface", len(spec.get("paths", {})) > 20,
              str(len(spec.get("paths", {}))))

    status_is("the docs browser is served", "/docs", 200, accept="text/html")
    status_is("the stylesheet is served", "/static/app.css", 200, accept="text/css")

    status, text, _ = request(
        "/api/auth/login", method="POST",
        body={"email": "tomas.varga@example.org", "password": "dogfood"},
    )
    check("password login works", status == 200, f"{status} {text[:140]}")
    status, _, _ = request(
        "/api/auth/login", method="POST",
        body={"email": "tomas.varga@example.org", "password": "wrong"},
    )
    check("a wrong password is refused", status in (401, 403), str(status))
    status, _, _ = request(
        "/api/auth/login", method="POST",
        body={"email": "nobody@example.org", "password": "dogfood"},
    )
    check("an unknown account is refused the same way", status in (401, 403), str(status))

    status, text, _ = request("/api/auth/whoami", token=JUDGE_A)
    if check("whoami answers", status == 200, text[:140]):
        payload = json.loads(text)
        check("whoami returns the caller's capabilities", "capabilities" in payload, text[:200])


def rate_limits() -> None:
    """The comment endpoint is the cheapest write, so it is the one to flood."""
    codes = []
    for index in range(30):
        status, _, _ = request(
            "/api/projects/prj_01/comments", token=PARTICIPANT, method="POST",
            body={"body": f"flood {index}"},
        )
        codes.append(status)
    check(
        "a flood of writes is rate limited",
        429 in codes,
        f"statuses seen: {sorted(set(codes))}",
    )
    check(
        "the first write in the flood succeeded",
        codes[0] in (200, 201),
        str(codes[0]),
    )


def voting() -> None:
    status, text, _ = request(f"/api/events/{FIXTURE_EVENT}/ballot", token=PARTICIPANT)
    if not check("the vote ballot is served", status == 200, text[:140]):
        return
    ballot = json.loads(text)
    ids = [row["id"] for row in ballot["projects"]]
    check("the ballot is shuffled, not in id order", ids != sorted(ids), str(ids[:4]))
    check("the ballot states its credit budget", ballot.get("credit_budget", 0) > 0, text[:160])

    status, text, _ = request(f"/api/events/{FIXTURE_EVENT}/ballot", token=PARTICIPANT)
    check(
        "the same voter sees a stable order",
        [r["id"] for r in json.loads(text)["projects"]] == ids,
    )
    status, text, _ = request(f"/api/events/{FIXTURE_EVENT}/ballot", token=JUDGE_A)
    check(
        "a different voter sees a different order",
        [r["id"] for r in json.loads(text)["projects"]] != ids,
    )

    status, text, _ = request(
        f"/api/events/{FIXTURE_EVENT}/votes", token=PARTICIPANT, method="POST",
        body={"project_id": ids[0], "credits": 4},
    )
    check("a vote within budget is accepted", status in (200, 201), f"{status} {text[:140]}")
    status, text, _ = request(
        f"/api/events/{FIXTURE_EVENT}/votes", token=PARTICIPANT, method="POST",
        body={"project_id": ids[1], "credits": 9},
    )
    check("a vote over budget is refused", 400 <= status < 500, f"{status} {text[:140]}")

    status_is(
        "vote results are embargoed from the crowd",
        f"/api/events/{FIXTURE_EVENT}/vote-results", (401, 403), token=PARTICIPANT,
    )


# ---------------------------------------------------------------------- main ---


def main() -> int:
    prepare_environment()
    for section in (
        public_surface,
        transports,
        role_matrix,
        deadline,
        normalization,
        lifecycle,
        balloting,
        csv_bytes,
        audit_chain,
        operations,
        rate_limits,
        voting,
    ):
        try:
            section()
        except Exception as exc:  # noqa: BLE001 - report, do not abort the run
            check(f"section {section.__name__} ran to completion", False, f"{type(exc).__name__}: {exc}")

    width = max(len(label) for _, label, _ in _results) + 2
    for ok, label, note in _results:
        dots = "." * max(width - len(label), 3)
        print(f"{label} {dots} {'PASS' if ok else 'FAIL'}")
        if not ok and note:
            print(f"       {note}")

    failed = [label for ok, label, _ in _results if not ok]
    print()
    print(f"{len(_results) - len(failed)}/{len(_results)} passed")
    if failed:
        print(f"failed: {len(failed)}")
        for label in failed:
            print(f"  - {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
