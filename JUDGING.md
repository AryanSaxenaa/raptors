# Judging

## Assignment

Judges are scoped to tracks (`judge_tracks`). Assignments are generated track-locally with conflict-of-interest skipping (team membership), least-loaded-first ordering, and duplicate projects skipped from new slots but left in the database.

Target reviews per project come from `events.reviews_per_project` (3 on the fixture event).

## Rubric

Criteria are rows in `rubric_criteria` with organizer-set weights. Changing weights bumps `rubric_version` and invalidates cached results so a mid-event rubric edit cannot leave a stale leaderboard.

Ballots store per-criterion scores in `score_criteria` on a 1–5 scale (the declared scale; fixture data happens to use 2–5 only).

## Cross-judge normalization

Raw weighted means favour harsh or generous judges. This portal uses a two-stage correction:

1. **Shrunken scale** — per-judge standard deviation is pulled toward the pool:  
   `σ̃ = (n·σ + k·σ_pool)/(n + k)` with `k = 5`, so σ is never zero (handles `jdg_07`, who scored all 4s).

2. **Additive ridge model** — fit `y_ij = μ + p_i + b_j` with alternating least squares,  
   `λ_project = 1`, `λ_judge = 3`. Judges with one ballot (`jdg_01`, `jdg_23`) get partial bias identification, not a fabricated full correction.

Methods exposed: `raw`, `shrunken_z`, `additive_ridge` (default).

### Proof

- Text: `docs/normalization-proof.txt` and `GET /api/organizer/normalization-proof`
- CLI: `python -m dogfood.normalize --proof --fixtures fixtures.json`
- Tests: `pytest tests/test_normalize.py`

On fixture data, between-judge spread drops by roughly 40% and ranks move (see proof artefact for exact numbers).

## Duplicates

`prj_41` is a second submission from team `tm_07` matching `prj_07`. It is flagged and excluded from ranking while `exclude_duplicates` is on; its nine review slots still inform judge calibration.

## Pairwise mode (not shipped)

A Bradley–Terry / Thurstone-style pairwise layer would compare projects within track after calibration, which fits sponsor “pick one of two” flows. We did not ship it this weekend: the brief’s Hard bonus list says to pick one normalization or pairwise extension and nail it, not half-do both. Normalization is the harder statistical gap in the incumbent platforms; pairwise remains a documented next step.
