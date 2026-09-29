# Raptors

The judging platform we would actually run.

Isolated ballots, a weighted rubric, documented cross-judge calibration, quadratic community voting, and a hash-chained audit trail. Built for [DOGFOOD 2026](https://dogfoodhack.com): FastAPI, SQLite, server-rendered HTML, JSON for every write. No cloud account, no hosted database, no auth vendor.

```bash
docker compose up --build
```

Portal: [http://localhost:8080](http://localhost:8080)

**Claimed and verified: T1 and T2.** T3 and T4 ship in this repo; they are not claimed in `.dogfood.toml` because `run.py` cannot verify them. That is the honest receipt.

---

## What it is

Hackathon judging is a data problem wearing a party hat. Incumbents ship a gallery and a CSV and then stop: they cannot weight criteria, they will not publish how they normalize, community votes are conceded to be gameable, and none of them has a public API.

Raptors is the rest of that product:

| Stage | What you get |
| --- | --- |
| Teams | Invite codes, not a mailing list |
| Submissions | Full field set; drafts until the deadline; the deadline actually holds |
| Gallery | Public, searchable, filterable; titles in the HTML so the checker can grep them |
| Assignment | Track-scoped, conflict-free, least-loaded first |
| Scoring | Organizer-weighted rubric; judges see only their queue |
| Isolation | 25-cell role matrix in `security.py`, denied at the API, audited |
| Normalization | Shrunken scale + ridge additive model; fixture proof committed |
| Voting | Quadratic credits; shuffled ballots; results embargoed until publish |
| Certificates | Hash-anchored JSON anyone can fetch; not a fake PKI |
| Archive | CSV at every stage, full event JSON in and out, hash-chained audit log |

---

## One command

```bash
docker compose up --build
```

That is the product. Image build needs network once (`apt-get`, `pip`). After that the container uses SQLite on a volume and bundled `fixtures.json`. No outbound calls except webhooks an organizer registered.

Local, without Docker:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
set PYTHONPATH=src              # export PYTHONPATH=src
set DOGFOOD_DEV_TOKENS=1
python -m dogfood init
python -m dogfood serve
```

Seeded demo logins (password `dogfood` when tokens are on): organizer, judge_a, judge_b, participant. Tokens also work as `Cookie: df_session=…` or `Authorization: Bearer …` — the values in `.dogfood.toml`.

---

## Receipt

```
python run.py .dogfood.toml
```

Committed at [`acceptance-report.txt`](acceptance-report.txt):

```
claimed T1 T2, verified T1 T2
```

All seven checker lines PASS. The suite never logs in; it attaches the headers we printed at boot. `peer_scores` is an explicit URL (`/api/judge/scores?judge=jdg_01`) so judge B probing judge A is a real cross-judge read, not an empty own-list 200.

Our tests beyond the checker:

```bash
python -m pytest tests/ -q --ignore=tests/smoke.py
python tests/smoke.py            # black-box; resets the local DB first
```

---

## How far we climbed

**T1 — Core.** Auth and sessions. Five roles (visitor, participant, judge, organizer, admin). Events with dates, tracks, and prizes. Team invite codes. Draft-and-edit until close. Deadline refused **before** body validation. Public gallery with search and track filter. Submission fields the brief lists as stable across platforms.

**T2 — Judging.** Invite and assign (batch at seed, algorithmic top-up). Weighted, per-event rubric. Role isolation in the backend, including track scope and assignment. Organizer progress (who has not started, which projects are thin). Cross-judge normalization, documented in [`JUDGING.md`](JUDGING.md) and proven on the fixture. CSV at every stage.

**T3 — Public (shipped, not claimed).** Quadratic voting (influence = √credits). Comments. Results hidden from everyone but organizers until publish. Ballot order shuffled per voter. Rate limits, duplicate detection, audit trail an organizer can read without a database client.

**T4 — Stretch (shipped, not claimed).** REST API + OpenAPI (`/docs`, `/openapi.json`). Webhooks, HMAC-signed, outbox so a dead endpoint cannot stall a ballot. Judge participation records and project certificates, publicly fetchable at `/api/records/{hash}`. Embeddable gallery (`/embed/gallery`, `/static/embed.js`). Bulk import and export so an organizer can leave.

Bonuses we nailed: **normalization proof**, **threat model**, **API-first**. Bonus we did not start: pairwise / Bradley–Terry. The brief says pick one hard bonus and finish it.

---

## What this does not do yet

- **Pairwise judging** — sketched in `JUDGING.md`, not implemented. Normalization is the gap every incumbent claims and none publishes; that is the hard bonus we took.
- **X.509 certificates** — records are hash-anchored JSON, not a public-key infrastructure.
- **T3/T4 in `.dogfood.toml`** — still only T1/T2 claimed. Claiming further would print `claimed but not verified` on a receipt that is otherwise clean.
- **Organizer HTML for every config knob** — prizes, custom questions, and rubric rows are full API surfaces; the setup page covers events, tracks, judges, and the voting window.
- **Demo video** — outline at [`docs/demo-video-outline.md`](docs/demo-video-outline.md). Record it before you submit. The portal is ready; the clip is the remaining human deliverable.
- **Production hardening** — `DOGFOOD_DEV_TOKENS=1` is on in Docker so the checker can attach cookies. Set it to `0` for a real event. See `THREAT-MODEL.md`.

---

## Surfaces

| Who | Where |
| --- | --- |
| Anyone | `/` `/projects` `/login` `/docs` |
| Participant | `/teams` `/projects/new` gallery vote |
| Judge | `/judge` `/judge/projects/{id}` |
| Organizer | `/organizer` `/organizer/setup` `/organizer/results` `/organizer/audit` `/organizer/webhooks` |
| Embed | `/embed/gallery` + `/static/embed.js` |
| Records | `/api/records/{hash}` `/certificates/{project_id}` (after publish) |

Nav hides pages the signed-in role cannot use. Isolation is still a 403 if you type the URL.

---

## Why the shape

- **Gallery is server-rendered.** `run.py` greps raw HTTP for fixture titles. A React shell looks perfect and fails T1.
- **One write surface.** The UI `fetch()`es `/api/*`. There is no privileged form-post path.
- **Deadline before validation.** A closed event returns `submissions_closed`, even on malformed JSON.
- **Matrix in one file.** `src/dogfood/security.py`. Tests walk all 25 cells over HTTP.
- **Normalization is published.** Shrunken per-judge scale (never divide by zero on the flat judge) plus ridge ALS. Proof: `docs/normalization-proof.txt`, `GET /api/organizer/normalization-proof`.
- **Duplicates are annotated, not deleted.** `prj_41` is out of the ranking; those ballots still calibrate the judges who saw both copies.

Deeper: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`DATA-MODEL.md`](DATA-MODEL.md), [`JUDGING.md`](JUDGING.md), [`THREAT-MODEL.md`](THREAT-MODEL.md). Engineering decisions: [`PLAN.md`](PLAN.md). Spec reading: [`INTEL.md`](INTEL.md). Forensic checklist: [`SUBMISSION.md`](SUBMISSION.md).

---

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOGFOOD_DEV_TOKENS` | off | Fixed session tokens for `.dogfood.toml` |
| `DOGFOOD_DB` | `var/dogfood.sqlite3` | SQLite path (Docker: `/data/dogfood.sqlite3`) |
| `PYTHONPATH` | — | Must include `src` for local runs |
| `DOGFOOD_WEBHOOK_WORKER` | on in `serve` | Background HMAC delivery; off in pytest |

License: MIT. Leave with your data: [`docs/migration.md`](docs/migration.md).
