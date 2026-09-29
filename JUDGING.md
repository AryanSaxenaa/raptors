# Judging

This is the document the 25% **Judging Integrity** criterion asks for: assignment, scoring maths, normalization, and the isolation rules. The numbers below are from the published `fixtures.json` (126 ballots, 41 projects, 30 judges) unless stated otherwise. Reproduce them with:

```
python -m dogfood.normalize --proof --fixtures fixtures.json
```

or `GET /api/organizer/normalization-proof` as an organizer. The same artefact is committed at `docs/normalization-proof.txt`.

## What a judge actually does

A judge signs in, opens `/judge`, and sees only the projects **assigned to them in their tracks**. Each row is one click from a ballot. The ballot asks for 1–5 on every criterion in `rubric_criteria` for that event, plus optional written feedback. Submitting calls `POST /api/judge/scores` — the same endpoint an external client would use. There is no privileged form-post path.

A judge never sees:

- another judge’s numeric ballots (`peer_scores` denied at the API);
- a project outside their tracks (`assert_track_visible`);
- a project they were not assigned (`assert_assigned`);
- the unpublished leaderboard (`results_embargoed`).

Each of those denials is a 401/403 with an RFC 9457 `code` and an `authorization.denied` row in the audit log. Hiding a button in HTML is not isolation; curl is.

## Assignment

Code: `src/dogfood/assignment.py`. Constraints, in this order:

1. **Track scope.** A judge is only assigned inside `judge_tracks`. The fixture set has zero of 126 ballots crossing a track boundary. The T2 rule (“a track judge must never see another track”) is therefore also an assignment invariant, not only a read-time check.
2. **Conflict of interest.** A judge is never assigned a project whose team they belong to.
3. **Coverage.** Eligible projects are topped up to `events.reviews_per_project` (3 on the fixture event).
4. **Balance.** Among eligible judges, least-loaded first. Ties break on judge id so the same input always produces the same plan.

Duplicates (`prj_41`) are skipped when topping up. Three judges reviewed both copies of *Dry Harbour*, so one team consumed 9 of 126 review slots. Scheduling more reviews against a known duplicate spends a scarce resource on a project that will not be ranked.

Track capacity is reported, not silently absorbed. `trk_01` and `trk_08` have 3 judges for 6 projects each; `trk_04` has 8 judges for 5 projects. A perfectly balanced global load is impossible; the organizer dashboard shows where the shortfall is (`judges_not_started`, `under_reviewed`, histogram of reviews per project).

Assignment is both **batch** (fixture seed writes the published assignments) and **algorithmic** (`POST /api/organizer/assignments/generate` tops up remaining slots).

## Rubric and scoring maths

Criteria are rows in `rubric_criteria`: `key`, `label`, `weight`, `min_value`, `max_value`. They are not constants in code. Changing weights bumps `events.rubric_version` and invalidates `results_cache`, so a mid-event edit cannot leave a stale leaderboard.

A ballot is one `scores` row plus one `score_criteria` row per criterion. Values are constrained `BETWEEN 1 AND 5` (the declared scale; fixture data happens to use 2–5 only). Unknown criterion keys are rejected at write time — they never reach the normalizer.

A ballot collapses to one number with the organizer’s weights, renormalised over criteria actually present:

\[
y_{ij} = \frac{\sum_k w_k\, s_{ijk}}{\sum_k w_k}
\]

Missing a criterion does not silently penalise the project; it stays on the 1–5 scale. On the fixture event all three weights are 1.0 (`functionality`, `quality`, `innovation`).

## The problem with averaging

Thirty judges, 126 ballots. The most generous judge averages **4.22**; the harshest **2.00** — a **2.22-point gap** on a 5-point scale. Loads run from 1 ballot (`jdg_01`, `jdg_23`) to 11 (`jdg_24`). `jdg_07` scored every criterion of every project a 4: sample standard deviation **exactly 0**. Eight projects have 2 reviews; four have 5.

A plain mean treats a generous 4 and a harsh 4 as the same evidence. A per-judge z-score divides by zero on `jdg_07` and maps the two single-ballot judges to 0.0, throwing their observations away. Z-scores are also not valid here: track-restricted assignment means no two judges saw a comparable sample, so their sample moments are not comparable quantities.

Commercial platforms either cannot weight criteria at all or advertise “automatic normalization” without publishing the method. This portal publishes both the method and the fixture proof.

## Normalization (two stages)

Code: `src/dogfood/normalize.py`. No third-party solver. Methods: `raw`, `shrunken_z`, `additive_ridge` (default). Organizer selects via `events.normalization_method`; all three are always computed for export.

### Stage 1 — shrunken scale

\[
\tilde{\sigma}_j = \frac{n_j\,\sigma_j + k\,\sigma_{\mathrm{pool}}}{n_j + k},\qquad k = 5
\]

\(\tilde{\sigma}_j\) is never zero because \(\sigma_{\mathrm{pool}}\) is not zero. `jdg_07` gets a location term and **zero discriminative weight**: a ballot with no relative information should not move ranks. That is a property of the estimator, not a special case.

At \(k=5\), a judge needs about five ballots before their own dispersion outweighs the pool, matching the fixture median load of 3.

### Stage 2 — ridge additive model

\[
y_{ij} = \mu + p_i + b_j
\]

fitted by alternating least squares on **observed cells only**, with \(\lambda_{\mathrm{project}} = 1\), \(\lambda_{\mathrm{judge}} = 3\). A judge with 11 ballots gets an almost unpenalised bias; a judge with 1 ballot gets \(b_j\) near zero, because one observation cannot separate judge bias from project quality.

The same ridge applies to project effects: a project with 2 reviews is pulled toward the mean more than one with 5. Partial pooling, not a confidence interval bolted on afterwards. Standard errors on the leaderboard are \(\mathrm{se} = \hat{\sigma}/\sqrt{n}\); projects below 3 reviews are flagged low-confidence (`!` in the proof).

### What the fixture proof shows

| Quantity | Value |
| --- | --- |
| Observations / projects / judges | 126 / 41 / 30 |
| Pooled mean / sd | 3.5661 / 0.6483 |
| Between-judge \(\sigma\) raw | 0.4127 |
| Between-judge \(\sigma\) after calibration | 0.2449 |
| Reduction | **40.7%** |
| ALS iterations | 24, converged, residual sd 0.4873 |
| Ranked projects | 40 (`prj_41` excluded) |

Largest rank movements: *Small Meadow* and *Flat Meadow* drop 9 places after calibration; *Flat Relay* rises 6. Raw rank is not the same as calibrated rank — that is the point of doing this.

`prj_41` (*Dry Harbour*, duplicate of `prj_07`): **excluded from ranking**, **ballots retained for calibration**. Dropping those ballots would bias the judges who saw both copies.

The brief site's FIG. 03 (`σ = 0.94 → 0.31`) is illustrative. On `fixtures.json` the population stdev of per-judge means is **0.4127** (sample stdev ≈ 0.42). The proof artefact states that so a reviewer is not chasing the cartoon number.

The same artefact also fits a **labelled synthetic panel**: same (judge, project) cells as the fixture, scores generated from known \(p_i\) and \(b_j\). That is validation, not a substitute for the fixture run. It is there to show the estimator recovers a planted effect — Kendall τ vs true ranking improves on raw means, and recovered project effects / judge biases correlate with truth — rather than only that spread fell.

## Isolation (the 25-cell matrix)

The website publishes a 5×5 matrix. `run.py` checks three cells. This portal implements all 25 in `security.py` `ROLE_MATRIX` and walks them over HTTP in `tests/test_role_matrix.py`.

| Actor | Own scores | Peer scores | Other track | Aggregate | Audit log |
| --- | --- | --- | --- | --- | --- |
| visitor | ✗ | ✗ | ✗ | ✗ | ✗ |
| participant | ✗ | ✗ | ✗ | ✗ | ✗ |
| judge | + | ✗ | ✗ | ✗ | ✗ |
| organizer | + | + | + | + | + |
| admin | + | + | + | + | + |

`+` permitted at the API. `✗` denied at the API (not only in the UI), audited as `authorization.denied` with a machine-readable `reason_code` (`peer_scores_denied`, `track_hidden`, …).

## Audit trail

Append-only `audit_log`, hash-chained: `entry_hash = sha256(prev_hash || canonical_json(payload))`. No UPDATE or DELETE exists against this table. `GET /api/audit/verify` walks the chain. Organizers read it at `/organizer/audit` without a database client. The acceptance suite’s peer-score probe becomes a visible row naming judge B and `peer_scores_denied`.

## Records and certificates

- **Judge participation record** — hash-anchored JSON of reviews assigned vs completed, track list, and the audit chain head at issuance. Issued once, stored, and **publicly fetchable** at `GET /api/records/{record_hash}` (no scores leaked). The judge console downloads it.
- **Project certificate** — after the organizer publishes results, `GET /certificates/{project_id}` and `GET /api/projects/{id}/certificate` state title, team, track, and calibrated rank. Unpublished events refuse this.

These are not X.509 / CA-signed documents. They are canonical JSON plus a SHA-256 over the audit head, which anyone can recompute. That is the verifiable record the T4 brief asks for without inventing a PKI over a weekend.

## Pairwise mode (not shipped)

Gavel-style Bradley–Terry pairwise comparison is a genuine alternative: never ask for an absolute score, recover a ranking from “which of these two is better.” The Hard bonus list says pick **one** of normalization or pairwise and nail it. Normalization is the gap every incumbent claims and none publishes. Pairwise remains a documented next step, not a half-built second mode.

## Tests

| Claim | Test / artefact |
| --- | --- |
| Spread drops ~40% on fixtures | `tests/test_normalize.py`, `docs/normalization-proof.txt` |
| Labelled panel recovers planted \(p_i\), \(b_j\) | `test_labelled_panel_recovers_planted_effects` |
| `jdg_07` flagged, not NaN | `test_zero_variance_judge_is_flagged_not_nan` |
| `prj_41` excluded from ranking | `test_duplicate_excluded_from_ranking` |
| 25-cell matrix | `tests/test_role_matrix.py` |
| Peer isolation (run.py) | `GET /api/judge/scores?judge=jdg_01` as judge_b → 403 |
| Deadline before validation | `tests/test_deadline.py` |
