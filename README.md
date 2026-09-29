# Raptors

**A self-hosted hackathon submission and judging portal** — the part incumbents usually stop building after the gallery and a CSV export.

Built for [DOGFOOD 2026](https://dogfoodhack.com) against [`spec.md`](spec.md). FastAPI and SQLite, server-rendered HTML for reads, JSON for every write. No cloud account, no hosted database, no auth vendor.

| Receipt | |
| --- | --- |
| **Claimed & verified** | **T1 + T2** (see [`.dogfood.toml`](.dogfood.toml) and [`acceptance-report.txt`](acceptance-report.txt)) |
| **Also shipped** | T3 community voting and T4 API/webhooks/export (not claimed — `run.py` cannot verify them) |
| **License** | MIT |

---

## Quick start

```bash
docker compose up --build
```

Wait until the service is healthy (cold start is usually 9–30 seconds; healthcheck `start_period` is 20s):

```bash
docker compose ps          # portal → healthy
python run.py .dogfood.toml
```

Portal: [http://localhost:8080](http://localhost:8080) · API docs: [http://localhost:8080/docs](http://localhost:8080/docs)

Image build needs network once (`apt-get`, `pip`). **Runtime** uses local SQLite and bundled [`fixtures.json`](fixtures.json) — no outbound calls except webhooks you register.

**Local dev** (without Docker):

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use source .venv/bin/activate on Unix
pip install -r requirements.txt
set PYTHONPATH=src                # export PYTHONPATH=src
set DOGFOOD_DEV_TOKENS=1          # fixed tokens for run.py / .dogfood.toml
python -m dogfood init
python -m dogfood serve
```

Demo logins (password `dogfood` when dev tokens are on): organizer, judge_a, judge_b, participant. Same values work as `Cookie: df_session=…` or `Authorization: Bearer …`.

---

## What you get

### T1 — Core (verified)

- **Roles:** visitor, participant, judge, organizer, admin — enforced in the API, not only in the UI.
- **Events:** deadlines, tracks, prizes; team formation by **invite code**.
- **Submissions:** full reference field set; draft-and-edit until close; **deadline checked before body validation** so closed events cannot be bypassed with malformed JSON.
- **Gallery:** public, searchable, filterable; fixture titles appear in **server-rendered HTML** (what `run.py` greps).

### T2 — Judging (verified)

- Judge invite, track scope, assignment (seed batch + algorithmic top-up).
- **Weighted rubric** per event; organizer progress dashboard.
- **25-cell role matrix** in one file ([`src/dogfood/security.py`](src/dogfood/security.py)); peer scores return **403**, audited.
- **Cross-judge normalization** (shrunken scale + ridge additive model) with committed fixture proof — [`JUDGING.md`](JUDGING.md), [`docs/normalization-proof.txt`](docs/normalization-proof.txt).
- **CSV export** at every pipeline stage.

### T3 — Public (shipped, not claimed)

- **Quadratic voting** (influence ∝ √credits); ballot order shuffled per voter (seeded).
- **Voting access modes** on each event: `authenticated`, `email`, or `open` — enforced on ballot and vote APIs; gallery UI supports open/email.
- Comments; **results embargo** until publish (and voting closes before publish is allowed).
- Rate limits, duplicate detection (`prj_41` flagged, not deleted), hash-chained audit log.

### T4 — Stretch (shipped, not claimed)

- REST API + OpenAPI (`/docs`, [`docs/openapi.json`](docs/openapi.json)).
- **Webhooks:** HMAC-SHA256, outbox with retries (writes never block on remote HTTP).
- Judge participation records and project certificates — hash-anchored JSON at `/api/records/{hash}`.
- Embeddable gallery (`/embed/gallery`, `/static/embed.js`).
- **Bulk import/export** — richer `event.json` snapshot; see [`docs/migration.md`](docs/migration.md).

**Bonuses:** normalization proof (hard), threat model (medium), API-first (medium). Pairwise judging was deliberately not built.

---

## Repository layout

```
hackathonRaptors/
├── .dogfood.toml          # Checker config (routes, auth headers, honest tier claim)
├── acceptance-report.txt  # Committed output of run.py
├── fixtures.json          # Shared seed data (40 projects, 30 judges, …)
├── run.py                 # Spec acceptance suite (stdlib HTTP client)
├── docker-compose.yml     # One-command demo; DOGFOOD_DEV_TOKENS=1 for the checker
├── Dockerfile
├── spec.md                # Contract with the organizers (read first)
│
├── src/dogfood/           # Application package
│   ├── app.py             # Factory, bootstrap, /api/health
│   ├── schema.sql         # Hand-written DDL (no ORM)
│   ├── security.py        # Role matrix + deny() → audit
│   ├── seed.py            # Idempotent fixtures load
│   ├── normalize.py       # Calibration methods
│   ├── exports.py         # CSV + event JSON
│   ├── webhooks.py        # Outbox delivery worker
│   ├── routers/           # auth, events, projects, judging, community, organizer, web, webhooks
│   ├── templates/         # Jinja2 HTML
│   └── static/            # CSS, embed.js, assets
│
├── tests/                 # pytest (HTTP + matrix + integrity gates)
└── docs/                  # migration, normalization proof, openapi snapshot, …
```

Design docs (required by the brief): [`ARCHITECTURE.md`](ARCHITECTURE.md), [`DATA-MODEL.md`](DATA-MODEL.md), [`JUDGING.md`](JUDGING.md). Submission checklist: [`SUBMISSION.md`](SUBMISSION.md). Limits and production notes: [`THREAT-MODEL.md`](THREAT-MODEL.md).

---

## Who uses which surface

| Role | Primary pages |
| --- | --- |
| Anyone | `/` · `/projects` · `/login` · `/docs` |
| Participant | `/teams` · `/projects/new` · gallery vote (when mode allows) |
| Judge | `/judge` · `/judge/projects/{id}` |
| Organizer | `/organizer` · `/organizer/setup` · `/organizer/results` · `/organizer/audit` · `/organizer/webhooks` |
| Embed | `/embed/gallery` + `/static/embed.js` |

Nav hides routes your role cannot use; typing a URL still hits the same **403** as the API.

---

## Design choices (why it is shaped this way)

1. **Gallery is server-rendered** — client shells pass in a browser and fail T1 greps.
2. **One write surface** — the UI only `fetch()`es `/api/*`; no privileged form posts.
3. **Matrix in one place** — [`tests/test_role_matrix.py`](tests/test_role_matrix.py) walks all 25 cells over HTTP.
4. **Duplicates are annotated** — `prj_41` stays in the gallery and out of the ranking; its ballots still calibrate judges.
5. **Health means seeded** — `/api/health` requires fixture counts and matching `schema_meta.version`.

---

## Verify your checkout

**Organizer checker** (same as judges use):

```bash
python run.py .dogfood.toml
```

Expected footer: `claimed T1 T2, verified T1 T2` — seven lines PASS ([`acceptance-report.txt`](acceptance-report.txt)).

**Our test suite** (includes integrity gates beyond `run.py`):

```bash
python -m pytest tests/ -q --ignore=tests/smoke.py
python tests/smoke.py    # black-box lifecycle; resets local DB
```

---

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOGFOOD_DEV_TOKENS` | `0` | Fixed session tokens for `.dogfood.toml`; Docker sets `1` for the checker |
| `DOGFOOD_DB` | `var/dogfood.sqlite3` | SQLite path (Docker: `/data/dogfood.sqlite3` on a volume) |
| `PYTHONPATH` | — | Must include `src` for local runs |
| `DOGFOOD_WEBHOOK_WORKER` | on in `serve` | Background webhook delivery; off in pytest |

---

## What we deliberately did not build

- Pairwise / Bradley–Terry judging (we took the **normalization proof** hard bonus instead).
- CA-signed certificates (hash-anchored JSON only).
- Multi-tenant SaaS (one organizer, one database — see [`THREAT-MODEL.md`](THREAT-MODEL.md)).

Leave with your data: [`docs/migration.md`](docs/migration.md).
