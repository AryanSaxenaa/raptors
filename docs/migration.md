# Migration guide

## Leave with your data

1. As organizer, `GET /api/exports/event.json` — full snapshot (events, teams, projects, judges, scores).
2. Download stage CSVs from `/api/exports/{projects,teams,judges,assignments,scores,results,audit}.csv` if downstream tools need spreadsheets.
3. Copy the SQLite file (`DOGFOOD_DB`) for a byte-identical backup including audit chain and sessions.

## Arrive on a new host

1. `docker compose up --build` or `python -m dogfood init && python -m dogfood serve`.
2. `POST /api/imports/event.json` with the snapshot (organizer session required).
3. Run `python run.py .dogfood.toml` against the new base URL; update `base_url` and tokens in `.dogfood.toml`.
4. `GET /api/audit/verify` on the new host to confirm log integrity if you imported audit rows.

## Idempotent seed

`python -m dogfood init` and container restarts upsert fixture ids; they do not duplicate rows. Asserted in `tests/test_adversarial.py::test_seed_idempotent_on_second_bootstrap`.

## Schema version

`schema_meta.version` must match `SCHEMA_VERSION` in code. Health reports both values; mismatch returns not-ready.
