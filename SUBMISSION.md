# Submission readiness

Forensic audit against `spec.md` (the contract) and `dogfoodhack.com.md` (the brief). Written so a teammate can decide “ship or not” without re-reading the source.

**Verdict: the software is ready to submit. Record the 5-minute demo, then freeze.**

Do not claim T3 or T4 in `.dogfood.toml`. The checker cannot verify them. The report already closes `claimed T1 T2, verified T1 T2`. That is the clean receipt both documents reward.

---

## The five things that are actually required (`spec.md`)

| # | Requirement | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `docker compose up` → seeded portal, network off at **runtime** | **Ready** | `docker-compose.yml`, `Dockerfile` copies fixtures and runs `python -m dogfood init`. Build needs network once. |
| 2 | OSI-approved license | **Ready** | `LICENSE` (MIT) |
| 3 | Code from the event window | **You** | Repo history. Frameworks and AI are allowed. |
| 4 | `.dogfood.toml` with honest claims | **Ready** | `claimed = ["T1", "T2"]`. Pitch and peer_scores URL are explicit. |
| 5 | `acceptance-report.txt` committed | **Ready** | All seven lines PASS. Footer: `claimed T1 T2, verified T1 T2`. |

Plus the documents the website lists:

| Document | Status |
| --- | --- |
| `README.md` | What it does, how to run, what it does not |
| `ARCHITECTURE.md` | Request path, trust boundary, why SQLite |
| `DATA-MODEL.md` | Schema, import/export, why not nested documents |
| `JUDGING.md` | Assignment, weighted maths, normalization, fixture proof |
| 5-minute demo video | **Not in the repo.** Script: `docs/demo-video-outline.md`. This is the remaining deliverable. |

`THREAT-MODEL.md` is the medium bonus, not a required file. It is committed.

---

## Acceptance suite (`spec.md` File 3)

| Check | Route | Result |
| --- | --- | --- |
| T1 gallery public | `GET /projects` no auth | PASS |
| T1 fixture titles in body | same, grep | PASS |
| T1 closed event refuses submit | `POST /api/events/evt_01/projects` as participant | PASS (`submissions_closed` before validation) |
| T2 judge sees own scores | `GET /api/judge/scores` as judge_a | PASS |
| T2 judge cannot see peer scores | `GET /api/judge/scores?judge=jdg_01` as judge_b | PASS 403 |
| T2 participant blocked | `GET /api/judge/scores` as participant | PASS 403 |
| T2 CSV export | `GET /api/exports/results.csv` as organizer | PASS |

`peer_scores` is **not** left to fall back to `judge_scores`. That fallback is judge B reading their own empty list (200) and a false FAIL on a portal that isolates correctly. Documented in `.dogfood.toml` `[notes]`.

---

## Tier ladder (`dogfoodhack.com.md` §04)

### T1 Core — complete

- Authentication and sessions (`df_session` cookie or Bearer).
- Roles: visitor, participant, judge, organizer, admin (`security.py`, schema CHECK).
- Event creation with dates, tracks, prizes (prizes: API + seed; setup HTML covers dates/tracks/judges/voting window).
- Team formation by invite code (`/teams`, `POST /api/teams/join`).
- Draft-and-edit until deadline (`/projects/new`).
- Deadline enforcement that holds (`tests/test_deadline.py`: malformed JSON still 4xx closed).
- Public gallery with search and track filter (`/projects`).
- Submission field set from the brief: name, tagline, description, thumbnail, image gallery, video URL, repo, live link, tech tags, track, custom questions.

### T2 Judging — complete

- Judge invitation and assignment (seeded batch + `POST /api/organizer/assignments/generate`).
- Weighted, organizer-configurable rubric (`rubric_criteria`; version bump invalidates cache).
- Role isolation **in the backend**. All 25 matrix cells over HTTP (`tests/test_role_matrix.py`). Track judges cannot see another track. UI hiding a nav link is extra, not the control.
- Live progress dashboard (`/organizer`): who has not started, under-reviewed projects, track capacity.
- Cross-judge normalization, documented and defended (`JUDGING.md`, `docs/normalization-proof.txt`, labelled synthetic panel).
- CSV export at every stage (`projects`, `teams`, `judges`, `assignments`, `scores`, `results`, `audit`).

### T3 Public — shipped, not claimed

- Community voting with quadratic credits (influence = √credits). Per-event `voting_access`: authenticated, email-gated, or open-link — enforced on ballot and vote APIs; gallery UI supports email/open (`/organizer/setup`).
- Comments on gallery projects.
- Results hidden until publish; **publish refused until `voting_closes_at`**; votes and ballot blocked after publish.
- Randomised ballot order, seeded per voter (`GET /api/events/{id}/ballot`); same voting-window guards as POST.
- Anti-abuse: rate limits, duplicate detection (`prj_41`), hash-chained audit. Covered in `tests/test_integrity_gates.py`.

### T4 Stretch — shipped, not claimed

- REST API covering UI writes; OpenAPI at `/docs` and `docs/openapi.json` (CI diffs them).
- Webhooks, HMAC-SHA256, outbox with retries so delivery cannot block a write.
- Certificate and record generation (project certificate after publish; judge participation record).
- Signed, publicly verifiable records: `GET /api/records/{hash}`, `POST /api/records/verify`. Hash-anchored JSON, not X.509.
- Embeddable gallery widget.
- Bulk import and export (`GET/POST` event JSON). An organizer can leave.

---

## Bonuses (`dogfoodhack.com.md` §07)

| Challenge | Status |
| --- | --- |
| Normalization proof (Hard) | **Done.** Fixture σ 0.4127 → 0.2449 (40.7%). Labelled panel recovers planted effects. |
| Pairwise mode (Hard) | **Not started.** Deliberate. Brief: pick one hard bonus and nail it. |
| Threat model (Medium) | **Done.** `THREAT-MODEL.md` names stopped attacks and gaps. |
| API first (Medium) | **Done.** OpenAPI, UI writes go through `/api/*`. |

---

## Scoring criteria — where we win and where we do not

**Tier completion (40%).** Green receipt, honest claim. This is the floor we actually cleared.

**Judging integrity (25%).** This is the argument: 25-cell matrix, deadline-before-validation, documented ridge model, hash-chained audit, quadratic votes, threat model that lists what we did not stop.

**Adoptability (20%).** One command, seeded fixtures, MIT, migration doc, JSON in and out. Weakest remaining item: the demo video is not recorded yet.

**Code quality (15%).** Hand-written DDL, no ORM, tests that walk HTTP, INTEL/PLAN as the paper trail of why.

---

## Honest gaps (not bugs)

1. Setup HTML does not create prizes, custom questions, or rubric rows. The API does.
2. No pairwise judging.
3. Records are not CA-signed.
4. Docker demo leaves `DOGFOOD_DEV_TOKENS=1` so `run.py` works. Production default is `0`.
5. Demo video still to record (outline: `docs/demo-video-outline.md`).

---

## Before you hit submit

1. Record the demo against a fresh portal (`docs/demo-video-outline.md`). Show one API 403 in the same clip as the UI.
2. Confirm the GitHub repo is **public**.
3. Confirm `acceptance-report.txt` is the current `run.py` output against `docker compose up`.
4. Do **not** bump `claimed` past T1/T2.
5. Link the video where the submission form asks. Optional: one line in the README once the URL exists.

## One-command local verification

```bash
docker compose up --build
# in another terminal
python run.py .dogfood.toml
```
