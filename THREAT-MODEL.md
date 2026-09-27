# Threat model

Scope: a self-hosted hackathon portal operated by an organizer who controls the server. Not a multi-tenant SaaS threat model.

## What we mitigate

| Threat | Control |
| --- | --- |
| Judge reads another judge’s ballots | `peer_scores` denied at API; audited |
| Judge scores outside assigned track | `assert_track_visible` + assignment check |
| Participant edits after deadline | `submissions_closed` before body validation |
| Participant escalates via spoofed role | Role from session row, not request body |
| Organizer repudiates audit trail | Hash-chained `audit_log`; `GET /api/audit/verify` |
| Credential stuffing on login | scrypt password hashes; rate limits on comments/votes |
| Vote stuffing | Per-voter credit budget; quadratic influence; seeded ballot order |
| CSV formula injection | `csv.writer` quoting on export |
| CSRF on JSON API | Opaque bearer/cookie; optional `DOGFOOD_STRICT_ORIGIN` |

## What we do not claim

| Gap | Notes |
| --- | --- |
| Host compromise | Anyone with shell on the box can replace code or SQLite; audit chain detects DB tampering after the fact, not server takeover |
| Sybil voters | Open-link voting mode exists; strong identity requires auth or email verification per event policy |
| Judge collusion | Normalization reduces spread; it does not detect coordinated fraud |
| DDoS | No CDN or WAF; rate limits are application-level only |
| Secret dev tokens | `DOGFOOD_DEV_TOKENS=1` uses known tokens for acceptance; must be off in production |
| End-to-end encryption | Projects are stored in plaintext SQLite |

## Recommended production settings

- `DOGFOOD_DEV_TOKENS=0`
- HTTPS in front of Uvicorn
- Backups of `DOGFOOD_DB` and periodic `audit/verify` checks
- Rotate organizer passwords; do not commit `.env`
