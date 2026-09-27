# UI vs API coverage

Most writes use the JSON API from HTML pages (`ARCHITECTURE.md`). The table below lists primary **user-facing pages**; OpenAPI at `/docs` remains the full surface.

## Participant / public

| Flow | UI | API |
| --- | --- | --- |
| Gallery | `/projects` | `GET /api/projects` |
| Project + comments | `/projects/{id}` | `POST /api/projects/{id}/comments` |
| Submit | `/projects/new` | `POST /api/events/{id}/projects` |
| Teams | `/teams`, `/teams/join/{code}` | `POST /api/events/{id}/teams`, `POST /api/teams/join` |
| Community vote | `/vote` | `GET/POST /api/events/{id}/ballot`, `/votes` |
| Sign in | `/login` | `POST /api/auth/login` |
| Certificate | `/certificates/{id}` | `GET /api/projects/{id}/certificate` (after publish) |
| Public record | — | `GET /api/records/{hash}`, `POST /api/records/verify` |

## Judge

| Flow | UI | API |
| --- | --- | --- |
| Queue + ballot | `/judge`, `/judge/projects/{id}` | `POST /api/judge/scores` |
| Participation record | Button on judge console | `GET /api/judges/{judge_id}/record` (stable hash; public copy at `/api/records/{hash}`) |

## Organizer

| Flow | UI | API |
| --- | --- | --- |
| Progress | `/organizer` | `GET /api/organizer/progress` |
| Event setup | `/organizer/setup` | `POST/PATCH /api/events`, tracks, judges |
| Webhooks | `/organizer/webhooks` | `GET/POST/DELETE /api/webhooks` |
| Results / audit / exports | `/organizer/results`, `/organizer/audit` | CSV/JSON export routes |

## Embed

```html
<script src="https://your-host/static/embed.js" data-event="evt_01" data-height="480"></script>
```

Iframe document: `/embed/gallery?event=evt_01` (allows `frame-ancestors *`).

## Not implemented

Pairwise / Bradley–Terry judging (`JUDGING.md`).
