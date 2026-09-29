# Threat model

Scope: a **self-hosted** hackathon portal run by an organizer who controls the server. Not a multi-tenant SaaS. Honest lists score; heroic ones do not.

## What we mitigate

| Attack | Control | Evidence |
| --- | --- | --- |
| Judge reads another judge’s ballots | `peer_scores` denied at API | `run.py` T2; audit `peer_scores_denied` |
| Judge reads another track | `assert_track_visible` + assignment | `tests/test_role_matrix.py` |
| Judge scores an unassigned project | assignment check on ballot write | judging router |
| Participant edits after deadline | `submissions_closed` **before** body validation | `tests/test_deadline.py` (malformed JSON still 4xx closed) |
| Role spoofing in JSON | Role from session row only | `security.py` |
| Organizer repudiates history | Hash-chained `audit_log`; `/api/audit/verify` | `tests/test_adversarial.py` |
| Credential stuffing | scrypt; login is rate-limited by application limits on write surfaces | `security.py` |
| Comment spam | 20 comments / 5 minutes | `ratelimit.py` |
| Vote stuffing | Quadratic budget (9 credits); one `voter_key` per project; 30 votes / hour | `community.py` |
| Position bias on ballots | Seeded shuffle per voter | `GET /api/events/{id}/ballot` |
| CSV formula injection | `csv.writer` quoting | `tests/test_csv.py` |
| CSRF on JSON writes | Opaque credential; optional `DOGFOOD_STRICT_ORIGIN` | config |
| Webhook blocking writes | Outbox + background worker | `tests/test_webhooks_and_ui.py` |
| XSS on voting UI | DOM `textContent`, no `innerHTML` | vote template test |
| Deadline gaming via clock | Compare stored UTC close to server now; invalid timestamps rejected on write | `require_iso_ts` |
| Publish during voting | `results_published` blocked until `voting_closes_at` | `events.patch_event` |
| Cross-event track on edit | PATCH validates `track_id` belongs to project event | `projects.update_project` |
| Duplicate submission (same team + title) | Flag, keep, exclude from rank | `prj_41` |

## Voting modes

Events choose how a voter is identified: authenticated user id, email hash, or open-link IP/fingerprint hash. Open-link is the weakest. Organizers who need strong identity should require auth. Influence is \(\sqrt{\mathrm{credits}}\) per project so dumping the whole budget on one favourite has diminishing returns.

Results stay embargoed (`results_published = 0`) from participants and visitors. Organizers can always see tallies — that is the point of an embargo rather than a secret.

## What we do not claim

| Gap | Why |
| --- | --- |
| Host compromise | Shell on the box replaces code or SQLite. The audit chain detects **database** tampering after the fact, not rootkits. |
| Sybil voters on open links | New browsers, VPNs, email aliases. Policy: small community prize + auth-gated mode. |
| Coordinated judge collusion | Normalization reduces harsh/generous **spread**. It does not detect a ring agreeing on a winner. |
| DDoS / volumetric flood | No CDN/WAF. Application rate limits only. Put TLS and a reverse proxy in front for production. |
| Secret dev tokens | `DOGFOOD_DEV_TOKENS=1` is for the committed acceptance file. Production: `0`. |
| End-to-end encryption | Projects are plaintext SQLite. Disk encryption is the operator’s. |
| Multi-tenant isolation | One organizer, one database file. Ten events on one box share a process. |
| Pairwise judging | Not implemented (`JUDGING.md`). |
| PKI certificates | Records are hash-anchored JSON, not CA-signed. |
| Submission scraping | The gallery is **public by design** (T1). Robots can copy titles. That is the product. |
| Timing oracle on login | We do not claim constant-time user enumeration beyond scrypt cost. |

## Recommended production settings

- `DOGFOOD_DEV_TOKENS=0`
- HTTPS reverse proxy; `DOGFOOD_STRICT_ORIGIN=1` if browsers post from a known origin
- Backups of `DOGFOOD_DB`; periodic `GET /api/audit/verify`
- Rotate organizer passwords; do not commit secrets
- Prefer authenticated voting for prizes that attract stuffing
