# Architecture

## Request path

```
Browser or run.py
    → Uvicorn (single process)
    → FastAPI middleware (request id + JSON access log)
    → Router (HTML or /api/*)
    → deps.get_conn (SQLite per request, WAL)
    → security.resolve_identity + capability check
    → handler
    → audit.record on denials and sensitive writes
```

Reads that must be public (gallery, project detail) render with Jinja2. Every write goes through the JSON API; the UI uses `fetch()` with the same credentials a script would use. There is no form-post path with extra privileges.

## Trust boundary

Authentication is an opaque session token (`df_session` cookie or `Bearer`). Authorisation is the five-column matrix in `security.py`, plus track and assignment checks for judge routes. The client never sends a role name; the server resolves role from the session row.

Denials return RFC 9457 problem JSON with a stable `code` slug and append an `authorization.denied` row to the hash-chained audit log.

## Data store

One SQLite file (`DOGFOOD_DB`, default `var/dogfood.sqlite3`). Schema from `schema.sql`; no ORM. Bootstrap runs before the port binds so health and gallery never answer on an empty database.

## Normalization

Score calibration runs offline in `normalize.py`, cached in `results_cache`. Mutations that affect rankings invalidate the cache. Duplicate projects are excluded from ranking but their ballots remain in the judge-calibration fit.

## Decisions we would revisit

1. **SQLite at very large events** — fine for hackathon scale; would shard by event or move to Postgres only with measured need.
2. **Fixed dev tokens** — correct for acceptance reproducibility; production must set `DOGFOOD_DEV_TOKENS=0`.
3. **Pairwise judging** — not shipped; see `JUDGING.md` for the Bradley–Terry design we would add next.

## Deployment

`Dockerfile` seeds on build; `docker compose up` exposes port 8080 with a named volume for `/data`. Healthcheck hits `/api/health` and requires seeded counts.
