# Dogfood Portal

Self-hostable hackathon submission and judging platform for [DOGFOOD 2026](https://dogfoodhack.com). Python 3.12, FastAPI, SQLite, server-rendered gallery, JSON API for writes.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
set PYTHONPATH=src
set DOGFOOD_DEV_TOKENS=1
python -m dogfood init
python -m dogfood serve
```

In another terminal:

```bash
python run.py .dogfood.toml > acceptance-report.txt
python tests/smoke.py
```

Docker:

```bash
docker compose up --build
```

Portal: http://localhost:8080

## Acceptance (what `run.py` checks)

| Check | Route / behaviour |
| --- | --- |
| T1 gallery public | `GET /projects` → 200, fixture titles in HTML body |
| T1 fixture visible | First three fixture project names on page one |
| T1 deadline | `POST /api/events/evt_01/projects` as participant → 4xx, `submissions_closed` |
| T2 own scores | `GET /api/judge/scores` as judge_a → 200 |
| T2 peer isolation | `GET /api/judge/scores?judge=jdg_01` as judge_b → 401/403 |
| T2 participant blocked | `GET /api/judge/scores` as participant → 401/403 |
| T2 CSV | `GET /api/exports/results.csv` as organizer → 200, comma in header |

`.dogfood.toml` sets `claimed = ["T1", "T2"]` so the report footer is clean (`claimed T1 T2, verified T1 T2`). T3/T4 features ship in the repo but are not claimed in the config because the suite cannot verify them.

## Key design choices

- **Gallery on the server** — fixture titles must appear in the raw HTML response; client rendering would pass the grep check only in a browser.
- **`peer_scores` explicit** — without it, `run.py` falls back to `judge_scores` and judge B’s own empty list returns 200, failing isolation.
- **Deadline before validation** — closed events return `submissions_closed`, not field errors.
- **Role matrix in code** — `src/dogfood/security.py`; denials audited as `authorization.denied`.
- **Normalization** — shrunken per-judge scale (never zero) plus ridge-penalised additive model; proof at `/api/organizer/normalization-proof` and `docs/normalization-proof.txt`.
- **Duplicates** — `prj_41` flagged; excluded from ranking, ballots kept for calibration.

## Tests

```bash
set PYTHONPATH=src
python -m pytest tests/ -q
python tests/smoke.py    # black-box; use a fresh DB for strict counts
```

For a clean smoke run: stop the server, `python -m dogfood reset`, start `serve` again, then run smoke.

## Beyond the verified tiers

Shipped but not in `run.py`: community comments and rate limits, quadratic voting with per-voter ballot shuffle, bulk JSON import/export, OpenAPI, hash-chained audit log, judge participation records, threat-model notes in `THREAT-MODEL.md` (when present). Each is reachable via the API the UI uses.

Pairwise judging mode is intentionally not implemented; see `JUDGING.md` (when present) for the sketched Bradley–Terry extension.

## Layout

```
src/dogfood/          application
  security.py         role matrix and sessions
  normalize.py        calibration engine
  seed.py             fixture ingest
  routers/            HTTP surface
fixtures.json         sample event
run.py                acceptance checker
.dogfood.toml         routes and test credentials
INTEL.md / PLAN.md    audit notes (optional to commit)
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOGFOOD_DEV_TOKENS` | off | Fixed session tokens for `.dogfood.toml` / acceptance |
| `DOGFOOD_DB` | `var/dogfood.sqlite3` | SQLite path |
| `PYTHONPATH` | — | Must include `src` for local runs |

Seeded logins (when `DOGFOOD_DEV_TOKENS=1`): organizer `org_7f2a`, judge_a `jdg_a_91bc`, judge_b `jdg_b_44de`, participant `prt_2e88` — as `Cookie: df_session=…` or `Authorization: Bearer …`.
