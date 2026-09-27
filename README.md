# Dogfood Portal

Self-hostable hackathon submission and judging platform for [DOGFOOD 2026](https://dogfoodhack.com). Python 3.12, FastAPI, SQLite, server-rendered gallery, JSON API for writes.

**Submitting:** [SUBMISSION.md](SUBMISSION.md) lists required artefacts; [docs/demo-video-outline.md](docs/demo-video-outline.md) is a ~5 minute demo script.

## Requirement → artefact → test

| Requirement | Artefact | How to verify |
| --- | --- | --- |
| T1 public gallery + fixture titles | `GET /projects`, `routers/web.py` | `python run.py .dogfood.toml`; `pytest tests/test_acceptance_invariants.py` |
| T2 own vs peer judge scores | `security.py`, `GET /api/judge/scores` | `run.py`; `pytest tests/test_role_matrix.py` |
| T2 CSV export | `exports.py`, `GET /api/exports/*.csv` | `run.py`; `pytest tests/test_csv.py` |
| R14 deadline before validation | `routers/web.py` | `pytest tests/test_deadline.py` |
| R21 track isolation (25-cell matrix) | `security.py` `ROLE_MATRIX` | `pytest tests/test_role_matrix.py` |
| R30 audit trail | `audit.py`, `/organizer/audit`, `GET /api/audit/verify` | `pytest tests/test_adversarial.py`; portal after login |
| R41 import/export | `exports.py`, `docs/migration.md` | Organizer JSON + CSV routes; migration doc |
| R42 normalization proof | `JUDGING.md`, `docs/normalization-proof.txt`, `normalize.py` | `python -m dogfood.normalize --proof --fixtures fixtures.json`; `pytest tests/test_normalize.py` |
| R45 API-first | `/docs`, `/openapi.json`, `docs/openapi.json` | `python -m dogfood export-openapi` |
| R44 threat model | `THREAT-MODEL.md` | Read file (mitigations + explicit gaps) |
| R16 full submission fields | `DATA-MODEL.md`, `schema.sql`, `/projects/new` | Schema + form fields |
| Architecture | `ARCHITECTURE.md` | Request path + trust boundary |
| Scale (~400 projects) | `tests/test_scale.py` | `pytest tests/test_scale.py` |
| Duplicate handling | `seed.py`, `prj_41` | `pytest tests/test_duplicates.py` |

OpenAPI: [docs/openapi.json](docs/openapi.json) (also live at `/openapi.json` when serving).

## What this does not do yet

- **Pairwise judging** — Bradley–Terry mode sketched in `JUDGING.md`, not implemented.
- **Participant certificates** — judge participation records are hash-anchored JSON (see judge console); not an external signing workflow.
- **T3/T4 in `.dogfood.toml`** — still only **T1/T2 claimed** because `run.py` verifies those tiers only.
- **Production hardening** — dev tokens default on in local/Docker demo config; set `DOGFOOD_DEV_TOKENS=0` for real deployments.
- **DDoS / multi-tenant isolation** — see `THREAT-MODEL.md`.

## UI surfaces

| Page | URL |
| --- | --- |
| Teams | `/teams` |
| Community vote | `/vote` |
| Organizer setup | `/organizer/setup` |
| Webhooks | `/organizer/webhooks` |
| Embeddable gallery | `/embed/gallery` + `/static/embed.js` |

Details: [docs/ui-coverage.md](docs/ui-coverage.md).

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
python -m pytest tests/ -q --ignore=tests/smoke.py
python tests/smoke.py    # black-box; auto-resets DB on localhost before running
```

Docker:

```bash
docker compose up --build
```

Portal: http://localhost:8080

**Build vs run:** image build needs network once (`apt-get`, `pip`). After that, `docker compose up` uses only the container, SQLite on a volume, and bundled fixtures — no external services at runtime.

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

`.dogfood.toml` sets `claimed = ["T1", "T2"]` so the report footer is clean (`claimed T1 T2, verified T1 T2`). Extra T3/T4 work (comments, voting API, exports, audit) exists in the repo but is not claimed in the config because the checker cannot verify it.

## Key design choices

- **Gallery on the server** — fixture titles must appear in the raw HTML response; client rendering would pass the grep check only in a browser.
- **`peer_scores` explicit** — without it, `run.py` falls back to `judge_scores` and judge B’s own empty list returns 200, failing isolation.
- **Deadline before validation** — closed events return `submissions_closed`, not field errors.
- **Role matrix in code** — `src/dogfood/security.py`; denials audited as `authorization.denied`.
- **Normalization** — shrunken per-judge scale (never zero) plus ridge-penalised additive model; proof at `/api/organizer/normalization-proof` and `docs/normalization-proof.txt`.
- **Duplicates** — `prj_41` flagged; excluded from ranking, ballots kept for calibration.

## Tests

```bash
python -m pytest tests/ -q --ignore=tests/smoke.py   # 63 tests; ~10 min locally (each test re-seeds fixtures)
python tests/smoke.py    # black-box; 193 checks; use a fresh DB for strict counts
```

CI runs the same pytest command on push (`.github/workflows/ci.yml`). For a clean smoke run against a remote host, point `python tests/smoke.py http://host:port` at the target. On `localhost`, smoke resets the database first via `python -m dogfood reset`.

## Beyond the verified tiers

Shipped in code but not in `run.py`: community **comments** and **quadratic voting** (UI at `/vote`), **webhooks** (API + `/organizer/webhooks`), **embeddable gallery** (`/embed/gallery`, `embed.js`), bulk import/export, hash-chained audit log, judge participation records on the judge console.

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
ARCHITECTURE.md       request path and trust boundary
DATA-MODEL.md         schema and import/export
JUDGING.md            assignment, rubric, normalization
THREAT-MODEL.md       mitigations and non-claims
docs/migration.md     move between hosts
docs/ui-coverage.md   which flows have HTML vs API-only
docs/openapi.json     committed OpenAPI snapshot
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOGFOOD_DEV_TOKENS` | off | Fixed session tokens for `.dogfood.toml` / acceptance |
| `DOGFOOD_DB` | `var/dogfood.sqlite3` | SQLite path |
| `PYTHONPATH` | — | Must include `src` for local runs |

Seeded logins (when `DOGFOOD_DEV_TOKENS=1`): organizer `org_7f2a`, judge_a `jdg_a_91bc`, judge_b `jdg_b_44de`, participant `prt_2e88` — as `Cookie: df_session=…` or `Authorization: Bearer …`.
