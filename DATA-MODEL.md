# Data model

`fixtures.json` is **input**, not the schema. The published file is sparse (title, summary, repo, scores). The database carries the full field set the website lists as stable across platforms: name, tagline, long description, thumbnail, image gallery, hosted demo video URL, repository URL, live link, tech tags, track, organizer-defined custom questions.

Hand-written DDL lives in `src/dogfood/schema.sql`. There is no ORM. Every CHECK, UNIQUE, and index an operator relies on is visible in that file.

## Conventions

1. **Ids are opaque TEXT.** Fixture ids (`evt_01`, `prj_07`, `jdg_01`, `tm_07`) are stored verbatim so a record in the JSON file and a row in SQLite are the same object.
2. **Everything below `events` carries `event_id`.** Nothing is globally scoped; a second event cannot read the first by omission. `/projects` and `/api/projects` default to the fixture event (`evt_01`); pass `event` / `event_id` for the sandbox or another event.
3. **Timestamps are ISO-8601 UTC strings.** Deadline comparison uses parsed instants, not string sort, in `require_submissions_open`.
4. **JSON-in-TEXT** only where the list is bounded: `tech_tags`, webhook `actions`, custom question `options`. Relational data (images, criteria, members) is tables, not nested arrays.

## Identity

| Table | Role |
| --- | --- |
| `users` | One person. `role` CHECK in `visitor`, `participant`, `judge`, `organizer`, `admin`. Email unique on `lower(email)`. Passwords: scrypt, per-user salt. |
| `sessions` | Opaque `token` primary key. Cookie `df_session` or `Authorization: Bearer`. Role is read from this row, never from the request body. |

A judge is a **user** plus a per-event `judges` row. The role matrix has one subject type.

## Event configuration

| Table | Role |
| --- | --- |
| `events` | Deadlines, voting window, `voting_access` (`authenticated` \| `email` \| `open`), `results_published`, `reviews_per_project`, `normalization_method`, `exclude_duplicates`, `rubric_version`. Writes reject inverted timelines (close before open, vote before submissions close). |
| `tracks` | UNIQUE `(event_id, name)`. |
| `prizes` | Optional `amount_cents` / currency. |
| `rubric_criteria` | Weighted keys; replacing the set increments `rubric_version`. |
| `custom_questions` | Organizer-defined prompts (`text`, `longtext`, `url`, `select`, `boolean`). |

## Teams and submissions

| Table | Role |
| --- | --- |
| `teams` | `invite_code` UNIQUE. **No UNIQUE (event_id, name)** — fixtures repeat `OpenSignal`, `StillTrail`, `AmberSwitch` across different teams. Identity is the id; name collisions warn at create. |
| `team_members` | `owner` / `member`. |
| `projects` | Full field set; `status` in `draft`, `submitted`, `flagged_duplicate`, `withdrawn`. `submitted_at` set when leaving draft. |
| `project_images` | Gallery URLs, ordered. |
| `custom_answers` | Answers keyed by question id. |

Duplicates are **annotated, not deleted**:

```
duplicate_of TEXT REFERENCES projects (id)
duplicate_reason TEXT
status = 'flagged_duplicate'
```

`prj_41` points at `prj_07` (“same team and identical title”). Ranking excludes it when `exclude_duplicates = 1`; calibration does not.

Solo teams (13 in the fixture) have no minimum-member constraint.

## Judging

| Table | Role |
| --- | --- |
| `judges` | Per-event roster, invite code, status. |
| `judge_tracks` | Track scope. |
| `assignments` | Review queue. |
| `scores` | One ballot header (comment, timestamps). |
| `score_criteria` | `value INTEGER CHECK (value BETWEEN 1 AND 5)`. |
| `results_cache` | Serialized normalizer output keyed by `(event_id, method, rubric_version)`. |

## Community, audit, ops

| Table | Role |
| --- | --- |
| `comments` | Rate-limited; `hidden` flag. |
| `votes` | UNIQUE `(event_id, project_id, voter_key)`; `credits` for quadratic influence. |
| `rate_limits` | Sliding windows for comments and votes. |
| `audit_log` | Append-only, `prev_hash` / `entry_hash`. No UPDATE/DELETE in application code. |
| `webhooks`, `webhook_deliveries`, `webhook_outbox` | Signed POSTs; outbox with `attempts` / `next_try_at` retries so audit writes never block on HTTP. `webhook_deliveries.outbox_id` lets retries skip destinations that already succeeded for that event. |
| `issued_records` | Persisted judge records and project certificates, keyed by `record_hash`. |

Indexes exist on every foreign-key lookup used by the gallery, judge queue, and audit filters (`projects_gallery_idx`, `audit_action_idx`, …).

## Import and export

An organizer can leave. That is a requirement of Adoptability (20%), not a courtesy.

| Direction | Format | Route |
| --- | --- | --- |
| Out | RFC 4180 CSV, CRLF, no BOM | `GET /api/exports/{projects,teams,judges,assignments,scores,results,audit}.csv` |
| Out | Event JSON (config, projects with images/answers, assignments, votes, webhooks) | `GET /api/exports/event.json` |
| In | Same JSON snapshot (or `fixtures.json` unchanged) | `POST /api/imports/event.json` |
| Out | Byte-identical backup | copy `DOGFOOD_DB` |

CSV uses `csv.writer` quoting so formula injection (`=cmd`) is quoted. Round-trip of commas and quotes is tested in `tests/test_csv.py`.

Operational checklist: `docs/migration.md`. Seed is idempotent on fixture ids (`tests/test_adversarial.py::test_seed_idempotent_on_second_bootstrap`).

## Health and schema version

`schema_meta.version` must match `SCHEMA_VERSION` in code. `GET /api/health` reports both plus fixture counts. A process that is up with an empty database is **not** ready; the health check fails in that window so `run.py` never greps an empty gallery.

## Why this shape

Deeply nested “user.posts.comments” documents would cap at SQLite array-in-JSON practicality and make “update one ballot” a rewrite of the parent. Flat tables plus ids match how organizers actually query: “all scores for this judge”, “all projects in this track”, “audit rows for this denial”.
