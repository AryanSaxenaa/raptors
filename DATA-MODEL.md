# Data model

The submission field set follows the brief’s reference list (name/tagline, long description, media URLs, tech tags, track, custom questions). `fixtures.json` is input data, not the schema: the database carries the full field set even when a fixture row is sparse.

## Core tables (from `schema.sql`)

| Table | Purpose |
| --- | --- |
| `users` | Accounts; `role` CHECK in (`visitor` roles stored as participant/judge/organizer/admin) |
| `sessions` | Opaque tokens bound to users |
| `events` | Deadlines, rubric version, normalization method, duplicate policy |
| `tracks`, `prizes` | Event configuration |
| `teams`, `team_members` | Team formation; invite codes |
| `projects` | Submissions; `status`, `duplicate_of`, full URL fields |
| `rubric_criteria` | Per-event weighted criteria keys |
| `judges`, `judge_tracks` | Judge roster and track assignment |
| `assignments` | Review queue |
| `scores`, `score_criteria` | Ballots; `CHECK (value BETWEEN 1 AND 5)` |
| `results_cache` | Serialized normalization output keyed by method + rubric version |
| `votes`, `comments` | T3 community features |
| `audit_log` | Hash-chained append-only log |

Team names are **not** unique per event: `fixtures.json` repeats names (`OpenSignal`, `StillTrail`, `AmberSwitch`) across different teams. Identity is the team id.

Duplicate submissions are annotated, not deleted:

```sql
duplicate_of TEXT REFERENCES projects (id),
duplicate_reason TEXT,
status CHECK (... 'flagged_duplicate' ...)
```

## Import / export

| Direction | Format | Entry point |
| --- | --- | --- |
| Out | CSV per stage | `GET /api/exports/{stage}.csv` |
| Out | Full event JSON | `GET /api/exports/event.json` |
| In | Event JSON snapshot | `POST /api/imports/event.json` |

CSV uses `csv.writer` with CRLF and no BOM. See `docs/migration.md` for a practical move-between-hosts checklist.

## Fixture ids

Primary keys match `fixtures.json` (`prj_07`, `jdg_01`, …) so diffs between file and database are direct comparisons, not through a mapping table.
