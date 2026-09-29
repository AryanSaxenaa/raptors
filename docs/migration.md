# Migration guide

## Leave with your data

1. As organizer, `GET /api/exports/event.json` — snapshot of the event, teams, projects (including images and custom answers), judges, scores, prizes, custom questions, assignments, votes, and webhook URLs (secrets are not exported; import mints new ones).
2. Download stage CSVs from `/api/exports/{projects,teams,judges,assignments,scores,results,audit}.csv` if downstream tools need spreadsheets.
3. Copy the SQLite file (`DOGFOOD_DB`) for a byte-identical backup including audit chain and sessions. Audit rows are not in the JSON snapshot because the hash chain is append-only on the origin database.

## Arrive on a new host

1. `docker compose up --build` or `python -m dogfood init && python -m dogfood serve`.
2. `POST /api/imports/event.json` with the snapshot (organizer session required).
3. Run `python run.py .dogfood.toml` against the new base URL; update `base_url` and tokens in `.dogfood.toml`.
4. `GET /api/audit/verify` on the new host to confirm log integrity if you imported audit rows.

## Idempotent seed

`python -m dogfood init` and container restarts upsert fixture ids; they do not duplicate rows. Asserted in `tests/test_adversarial.py::test_seed_idempotent_on_second_bootstrap`.

## Schema version

`schema_meta.version` must match `SCHEMA_VERSION` in code (currently `"3"`). Health reports both values; mismatch returns not-ready. Additive columns (`voting_access`, outbox retry fields, `webhook_deliveries.outbox_id`) are applied by `apply_migrations()` on existing databases.
