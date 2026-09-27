# Submission checklist (DOGFOOD 2026)

Use this before you tag a release or hand the repo to judges. Items marked **automated** are already enforced in CI or committed reports.

## Required in the repository

| Item | Status | How to verify |
| --- | --- | --- |
| Public repo + license | You | `LICENSE` (MIT) |
| `.dogfood.toml` | **automated** | Committed; matches dev tokens when `DOGFOOD_DEV_TOKENS=1` |
| `acceptance-report.txt` | **automated** | `python run.py .dogfood.toml > acceptance-report.txt` |
| `fixtures.json` at repo root | **automated** | Present |
| `run.py` checker | **automated** | Same as acceptance report |
| Architecture / data / judging docs | **automated** | `ARCHITECTURE.md`, `DATA-MODEL.md`, `JUDGING.md` |
| Threat model | **automated** | `THREAT-MODEL.md` |
| OpenAPI snapshot | **automated** | `docs/openapi.json`; CI regenerates on push |
| Your tests beyond the checker | **automated** | `python -m pytest tests/ -q --ignore=tests/smoke.py` (63 tests; slow locally ~10 min; CI on push) |
| Adversarial smoke report | **automated** | `python tests/smoke.py > smoke-report.txt` (193 checks; resets DB on localhost) |

## Required outside the repository (you)

| Item | Notes |
| --- | --- |
| **5-minute demo video** | One lifecycle: create/submit → judge → publish results. Link in README or submission form when the site opens. |
| **Reachable team** | GitHub issues or email on the repo for judge follow-up. |

## Tier claim

- `.dogfood.toml` sets `claimed = ["T1", "T2"]` — matches a green acceptance footer (`verified T1 T2`).
- T3/T4 features exist in the codebase (voting, comments, exports, audit) but are **not** claimed in `.dogfood.toml` because `run.py` cannot verify them. Mention them in README under “Beyond the verified tiers” if you want credit for ambition without overclaiming in the receipt.

## One-command local verification

```bash
pip install -r requirements.txt
export PYTHONPATH=src DOGFOOD_DEV_TOKENS=1
python -m dogfood init && python -m dogfood serve &
python run.py .dogfood.toml > acceptance-report.txt
python -m pytest tests/ -q --ignore=tests/smoke.py
python tests/smoke.py > smoke-report.txt
```

Docker: `docker compose up --build` then point `.dogfood.toml` `base_url` at the container port.

## Known non-goals (documented, not bugs)

- Pairwise / Bradley–Terry judging (`JUDGING.md`)
- Externally signed participant certificates (judge records are hash-anchored JSON only)
- Production hardening with dev tokens off (`THREAT-MODEL.md`, `DOGFOOD_DEV_TOKENS=0`)

Implemented T4 extras (not claimed in `.dogfood.toml`): webhooks, embeddable gallery, organizer setup UI — see [docs/ui-coverage.md](docs/ui-coverage.md).
