# Architecture

A single-process FastAPI app, one SQLite file, Jinja2 for public reads, JSON for every write. No Redis, no Postgres, no auth vendor, no CDN. `docker compose up --build` is the product.

## Why this shape

The acceptance suite greps **raw HTTP bytes** of the gallery for fixture titles. A client-rendered shell looks perfect in a browser and fails that check. Server-rendered HTML makes the check pass by construction and keeps the gallery working with JavaScript off.

The same suite attaches a cookie header and never logs in. So authentication is one opaque token (`df_session` or `Bearer`), printed at boot when `DOGFOOD_DEV_TOKENS=1`. Production sets that to `0`.

Writes from the UI use `fetch()` to `/api/*`. There is no second, privileged form-post surface. “Every action the UI can take is available through the API” is an architecture property, not a README promise. OpenAPI is served at `/openapi.json` and committed as `docs/openapi.json`; CI diffs them.

## Request path

```
Browser, run.py, or curl
    → Uvicorn (one process, port 8080)
    → middleware: X-Request-Id + JSON access log
    → router (HTML under / or JSON under /api)
    → deps.get_conn  (SQLite, WAL, one connection per request)
    → security.resolve_identity  (session row → role)
    → capability / operation check
    → handler
    → audit.record on denials and sensitive writes
    → webhook outbox enqueue (no HTTP in the request)
```

Bootstrap (`schema + fixtures`) runs **before the socket binds**. A port that accepts traffic on an empty database is how the gallery check fails. `/api/health` reports seed counts, not merely “process alive”.

## Trust boundary

| Inside | Outside |
| --- | --- |
| Session token → user id → role | Request body `role` field (ignored) |
| `ROLE_MATRIX` + track + assignment | UI hiding a nav link |
| Deadline check before JSON validation | Disabling a submit button |
| Hash-chained `audit_log` | Container stdout |

Denials are RFC 9457 problem documents with a stable `code` (`peer_scores_denied`, `submissions_closed`, …). The same helper writes the audit row. One path for refuse-and-record.

## Data store

SQLite at `DOGFOOD_DB` (default `var/dogfood.sqlite3`; Docker uses `/data` on a named volume). WAL mode. Schema in `schema.sql`. Fine for hackathon scale (fixture: 41 projects; scale test: ~400). Would move to Postgres only with measured need, not because it sounds production-grade.

## Normalization and cache

`normalize.py` is pure Python, no solver dependency. Results are stored in `results_cache` keyed by event, method, and `rubric_version`. Score writes, rubric edits, duplicate decisions, and publish flags invalidate the cache so a graded GET never waits on ALS.

## Webhooks

Audit `record()` only inserts an **outbox** row in the same transaction. A daemon thread (`DOGFOOD_WEBHOOK_WORKER`, default on in `serve`, off in pytest) POSTs HMAC-SHA256 signed bodies with exponential backoff retries. A dead endpoint cannot stall a ballot save. Each delivery is keyed by `(outbox_id, webhook_id)`; destinations that already returned 2xx are not POSTed again when another destination still needs a retry. Failed destinations remain at-least-once. See `src/dogfood/webhooks.py`.

## Processes and deploy

| Command | Meaning |
| --- | --- |
| `python -m dogfood init` | Schema + seed |
| `python -m dogfood serve` | Bind 0.0.0.0:8080 after bootstrap |
| `python -m dogfood reset` | Recreate DB (smoke on localhost) |
| `python -m dogfood export-openapi` | Write `docs/openapi.json` |
| `docker compose up --build` | Image install + seed + healthcheck |

**Build** needs network once (`apt-get`, `pip`). **Run** does not: SQLite, fixtures, no outbound required except optional webhooks the organizer configured.

OSC 8 hyperlink is printed at boot so terminals that support it make `http://localhost:8080` clickable.

## Decisions we would revisit

1. **SQLite at multi-tenant SaaS scale** — out of scope; this is a self-hosted single-organizer box (`THREAT-MODEL.md`).
2. **Fixed dev tokens** — required for a committed `.dogfood.toml`; must be off in production.
3. **Pairwise judging** — not shipped; see `JUDGING.md`.
4. **External PKI for certificates** — records are hash-anchored JSON, publicly fetchable; not X.509.

## Related documents

- `DATA-MODEL.md` — tables, import/export
- `JUDGING.md` — assignment, maths, proof
- `THREAT-MODEL.md` — attacks stopped and not stopped
- `docs/ui-coverage.md` — HTML vs API surfaces
- `docs/migration.md` — leave and arrive
