# Demo video outline (~5 minutes)

Suggested script for the submission video. Record against a **fresh** portal (`python -m dogfood reset && python -m dogfood serve`).

1. **Intro (30s)** — What the portal is; show `acceptance-report.txt` and `smoke-report.txt` green in the repo.
2. **Public gallery (45s)** — `/projects` without login; fixture titles in HTML; search/filter.
3. **Participant path (60s)** — Login as participant; open demo event; create team (show name collision flag); draft project not in gallery; submit; appears in gallery.
4. **Judge isolation (60s)** — Judge A ballot; Judge B denied on `/api/judge/scores?judge=jdg_01` (403 + `peer_scores_denied`); organizer can read peer scores.
5. **Organizer (90s)** — Progress/assignments; normalized results (`/organizer/results`); normalization proof; duplicate `prj_41`; export CSV; `/organizer/audit` showing the denial row.
6. **Close (15s)** — `python run.py .dogfood.toml` PASS; link to docs and OpenAPI `/docs`.

Keep browser devtools or a second terminal visible for one API denial so judges see server-side enforcement, not UI-only hiding.
