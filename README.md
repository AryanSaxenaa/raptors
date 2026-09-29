# Raptors

**The judging platform we would actually run** — isolated ballots, a weighted rubric, documented judge calibration, and a public gallery that still works with JavaScript off.

Self-hosted. One Docker command. SQLite on disk. MIT. No cloud account, no hosted database, no auth vendor.

Built for [DOGFOOD 2026](https://dogfoodhack.com) against [`spec.md`](spec.md).

| | |
| --- | --- |
| **Claimed & verified** | **T1 + T2** — [`acceptance-report.txt`](acceptance-report.txt) footer: `claimed T1 T2, verified T1 T2` |
| **Also shipped** | T3 quadratic voting and T4 API / webhooks / export. Not claimed: `run.py` cannot verify them. |
| **Hard bonus** | Normalization proof — 40.7% spread reduction on the fixture panel ([`JUDGING.md`](JUDGING.md)) |
| **License** | MIT |

---

## Run it

```bash
docker compose up --build
```

Wait until healthy (cold start is usually 9–30 seconds):

```bash
docker compose ps          # portal → healthy
python run.py .dogfood.toml
```

Portal: [http://localhost:8080](http://localhost:8080) · API: [http://localhost:8080/docs](http://localhost:8080/docs)

Image **build** needs network once. **Runtime** uses local SQLite and bundled [`fixtures.json`](fixtures.json) — no outbound calls except webhooks you register.

Demo logins (password `dogfood` when dev tokens are on): `organizer`, `judge_a`, `judge_b`, `participant`. Same values work as `Cookie: df_session=…` or `Authorization: Bearer …`.

<details>
<summary>Local dev without Docker</summary>

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use source .venv/bin/activate on Unix
pip install -r requirements.txt
set PYTHONPATH=src                # export PYTHONPATH=src
set DOGFOOD_DEV_TOKENS=1          # fixed tokens for run.py / .dogfood.toml
python -m dogfood init
python -m dogfood serve
```

</details>

---

## Why this portal

Incumbents ship a gallery and a CSV. The failure mode is the rest: a judge who can read a peer’s ballot, a deadline that yields to malformed JSON, results that leak while voting is still open.

| What the brief actually scores | What is in this repo |
| --- | --- |
| **Honest claims** | `.dogfood.toml` claims only what `run.py` verifies. T3/T4 are built and tested, not advertised as checked. |
| **Judging integrity** | Peer scores are **403**, audited. Track isolation is server-side. 25-cell role matrix over real HTTP. |
| **Deadline is a property of the event** | Closed events refuse submissions *before* the body is parsed. |
| **Calibration you can replay** | Stage-1 variance shrinkage + ridge additive model. Fixture proof committed. Flat judges do not produce `NaN`. |
| **Leave with your data** | RFC 4180 CSV at every pipeline stage, plus a round-trip `event.json`. |

---

## What you get

### T1 — Core (verified)

- **Roles:** visitor, participant, judge, organizer, admin — enforced in the API, not only in the UI.
- **Events:** deadlines, tracks, prizes; team formation by **invite code**.
- **Submissions:** full reference field set; draft-and-edit until close.
- **Gallery:** public, searchable, filterable; **one event at a time** (fixture `evt_01` by default; sandbox is `/projects?event=evt_demo`); first fixture titles sit on page one; titles appear in **server-rendered HTML** (what `run.py` greps).

### T2 — Judging (verified)

- Judge invite, track scope, assignment (seed batch + algorithmic top-up).
- **Weighted rubric** per event; organizer progress dashboard.
- **25-cell role matrix** in [`src/dogfood/security.py`](src/dogfood/security.py); peer scores return **403**, audited.
- **Cross-judge normalization** with committed fixture proof — [`JUDGING.md`](JUDGING.md), [`docs/normalization-proof.txt`](docs/normalization-proof.txt).
- **CSV export** at every pipeline stage.

### T3 — Public (shipped, not claimed)

- **Quadratic voting** (influence ∝ √credits); ballot shuffled per voter.
- **Voting access:** `authenticated`, `email`, or `open` — enforced on ballot and vote APIs.
- **Results embargo:** cannot publish while voting is still open; ballots stop after publish.
- Rate limits, duplicate detection (`prj_41` flagged, not deleted), hash-chained audit log.

### T4 — Stretch (shipped, not claimed)

- REST API + OpenAPI (`/docs`, [`docs/openapi.json`](docs/openapi.json)).
- **Webhooks:** HMAC-SHA256, outbox with retries. Destinations that already returned 2xx are not POSTed again for that event.
- Hash-anchored judge records and project certificates at `/api/records/{hash}`.
- Embeddable gallery (`/embed/gallery`, `/static/embed.js`).
- **Bulk import/export** — [`docs/migration.md`](docs/migration.md).

**Bonuses shipped:** normalization proof (hard), threat model (medium), API-first (medium). Pairwise judging was deliberately not built.

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

## Design choices

1. **Gallery is server-rendered** — a client shell looks fine in a browser and fails T1 greps.
2. **One write surface** — the UI only `fetch()`es `/api/*`; no privileged form posts.
3. **Matrix in one place** — [`tests/test_role_matrix.py`](tests/test_role_matrix.py) walks all 25 cells over HTTP.
4. **Duplicates are annotated** — `prj_41` stays in the gallery and out of the ranking; its ballots still calibrate judges.
5. **Health means seeded** — `/api/health` requires fixture counts and matching `schema_meta.version`.
6. **Event records stay event-scoped** — the public gallery does not mix sandbox projects into the fixture event.

Design docs: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`DATA-MODEL.md`](DATA-MODEL.md), [`JUDGING.md`](JUDGING.md), [`THREAT-MODEL.md`](THREAT-MODEL.md). Checklist: [`SUBMISSION.md`](SUBMISSION.md).

---

## Verify your checkout

```bash
python run.py .dogfood.toml
```

Expected footer: `claimed T1 T2, verified T1 T2` — seven lines PASS.

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
| `DOGFOOD_STRICT_ORIGIN` | `0` | When `1`, mutating requests with a foreign `Origin` are rejected |

---

## What we deliberately did not build

- Pairwise / Bradley–Terry judging (we took the **normalization proof** hard bonus instead).
- CA-signed certificates (hash-anchored JSON only).
- Multi-tenant SaaS (one organizer, one database — see [`THREAT-MODEL.md`](THREAT-MODEL.md)).

Leave with your data: [`docs/migration.md`](docs/migration.md).
