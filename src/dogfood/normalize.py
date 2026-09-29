"""Cross-judge score normalization.

The problem, stated from the data in fixtures.json: thirty judges cast 126
ballots across 41 projects. The harshest judge averages 2.00 and the most
generous 4.22 -- a 2.22-point gap on a 5-point scale. Judge loads run from 1
ballot to 11. One judge (jdg_07) gave every criterion of every project she saw
a 4, so her standard deviation is exactly zero. Two judges cast a single ballot
each. Eight projects have 2 reviews; four have 5.

A plain average ignores the 2.22-point judge gap. A per-judge z-score divides
by zero on jdg_07, and maps the two single-ballot judges to exactly 0.0,
discarding their observations entirely. Per-judge standardisation is also not
valid here in the first place: with track-restricted assignment and loads from
1 to 11, no two judges saw a comparable sample of projects, so their sample
moments are not comparable quantities.

What this module does instead, in two stages:

  1. Shrunken scale correction. Each judge's spread is estimated as a
     precision-weighted blend of their own sd and the pooled sd,
         sigma_j = (n_j * sd_j + k * sd_pool) / (n_j + k)
     which is never zero because sd_pool is not zero. The division by zero is
     removed by construction rather than by a special case.

  2. A ridge-penalised additive model, y_ij = mu + p_i + b_j, fitted by
     alternating least squares over the observed cells only. The L2 penalty
     makes shrinkage a property of the objective: a judge with 11 ballots gets
     a nearly unpenalised bias estimate, a judge with 1 ballot gets b_j near
     zero, because with one observation judge bias and project quality are not
     separable and pretending otherwise is the error.

Three consequences worth naming, because they are choices and not accidents:

  * A zero-variance judge contributes a location term and zero discriminative
    weight. That is the correct treatment of a ballot that contains no
    information about relative merit -- not a bug to be patched.
  * The same ridge penalty applies to project effects, so a project with 2
    reviews is pulled toward the mean more than one with 5. Partial pooling,
    not a confidence interval bolted on afterwards.
  * Ballots cast on projects excluded from the ranking (duplicates) stay in
    the fitting data. Excluding a judge's observation would bias that judge's
    bias estimate. We exclude from the *ranking*, not from the *calibration*.

No third-party dependency. Cost is O(observations) per iteration.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

METHODS = ("raw", "shrunken_z", "additive_ridge")

# Shrinkage strength for per-judge mean and sd. At k = 5 a judge needs about
# five ballots before their own dispersion outweighs the pooled estimate, which
# matches the fixture's median load of 3 and keeps single-ballot judges from
# being rescaled on no evidence.
K_SHRINK = 5.0

# Ridge penalties. LAMBDA_JUDGE is the larger of the two: we are more willing
# to believe a project is genuinely good than that a judge is genuinely biased,
# because a project effect is identified by several judges while a judge effect
# with few ballots is confounded with the quality of what they were assigned.
LAMBDA_PROJECT = 1.0
LAMBDA_JUDGE = 3.0

MAX_ITER = 200
TOLERANCE = 1e-9

# Below this many reviews a project's score is reported but marked
# low-confidence. The brief's own target is 3 reviews per project.
LOW_CONFIDENCE_REVIEWS = 3


# ------------------------------------------------------------------ inputs ---


@dataclass(frozen=True)
class Observation:
    """One ballot, reduced to a single weighted value on the rubric scale."""

    judge_id: str
    project_id: str
    value: float


def weighted_value(criteria: dict[str, float], weights: dict[str, float]) -> float:
    """Collapse a ballot's criteria to one number using the rubric weights.

    Weights are renormalised over the criteria actually present, so a ballot
    missing a criterion stays on the same 1-5 scale as a complete one instead
    of being silently penalised. Criteria with no weight are ignored; the API
    rejects unknown criteria keys at write time, so they cannot arrive here.
    """
    total_weight = 0.0
    total = 0.0
    for key, value in criteria.items():
        weight = weights.get(key)
        if weight is None or weight <= 0:
            continue
        total += weight * float(value)
        total_weight += weight
    if total_weight == 0:
        # No weighted criteria on this ballot: fall back to the unweighted mean
        # so a rubric misconfiguration degrades instead of dividing by zero.
        values = [float(v) for v in criteria.values()]
        return statistics.fmean(values) if values else 0.0
    return total / total_weight


# ----------------------------------------------------------------- outputs ---


@dataclass
class JudgeDiagnostic:
    judge_id: str
    n_reviews: int
    raw_mean: float
    raw_sd: float
    shrunk_mean: float
    shrunk_sd: float
    scale_factor: float
    bias: float
    calibrated_mean: float
    is_flat: bool
    single_ballot: bool


@dataclass
class ProjectResult:
    project_id: str
    n_reviews: int
    raw: float | None
    shrunken_z: float | None
    additive_ridge: float | None
    std_error: float | None
    low_confidence: bool
    excluded: bool
    rank_raw: int | None = None
    rank_normalized: int | None = None
    rank_delta: int | None = None

    def score(self, method: str) -> float | None:
        return getattr(self, method)


@dataclass
class NormalizationResult:
    method: str
    projects: list[ProjectResult]
    judges: list[JudgeDiagnostic]
    observations: int
    judge_spread_before: float
    judge_spread_after: float
    residual_sd: float
    iterations: int
    converged: bool
    pooled_mean: float
    pooled_sd: float
    params: dict[str, float] = field(default_factory=dict)

    def ranked(self) -> list[ProjectResult]:
        """Projects in leaderboard order: excluded ones are not ranked."""
        included = [p for p in self.projects if not p.excluded]
        return sorted(
            included,
            key=lambda p: (-(p.score(self.method) or 0.0), p.project_id),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["method"] = self.method
        return payload


# ------------------------------------------------------------------- solver ---


def _population_sd(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def compute(
    observations: Iterable[Observation],
    *,
    method: str = "additive_ridge",
    all_project_ids: Iterable[str] | None = None,
    excluded_project_ids: Iterable[str] = (),
    k_shrink: float = K_SHRINK,
    lambda_project: float = LAMBDA_PROJECT,
    lambda_judge: float = LAMBDA_JUDGE,
) -> NormalizationResult:
    """Fit all three methods and return them together.

    All three are always computed, whatever `method` says: `method` only
    chooses the leaderboard ordering, and the results CSV carries every column
    so an organizer can diff them in a spreadsheet.
    """
    if method not in METHODS:
        raise ValueError(f"unknown normalization method: {method}")

    obs = list(observations)
    excluded = set(excluded_project_ids)
    project_ids = set(all_project_ids or ()) | {o.project_id for o in obs}

    if not obs:
        # A real event has this state for its first few hours, and a project
        # with no reviews has it forever. Report nulls rather than dividing by
        # a review count of zero.
        return NormalizationResult(
            method=method,
            projects=[
                ProjectResult(
                    project_id=pid,
                    n_reviews=0,
                    raw=None,
                    shrunken_z=None,
                    additive_ridge=None,
                    std_error=None,
                    low_confidence=True,
                    excluded=pid in excluded,
                )
                for pid in sorted(project_ids)
            ],
            judges=[],
            observations=0,
            judge_spread_before=0.0,
            judge_spread_after=0.0,
            residual_sd=0.0,
            iterations=0,
            converged=True,
            pooled_mean=0.0,
            pooled_sd=0.0,
            params={"k_shrink": k_shrink, "lambda_project": lambda_project,
                    "lambda_judge": lambda_judge},
        )

    values = [o.value for o in obs]
    pooled_mean = statistics.fmean(values)
    pooled_sd = _population_sd(values)

    by_judge: dict[str, list[float]] = defaultdict(list)
    for o in obs:
        by_judge[o.judge_id].append(o.value)

    # --- stage 1: shrunken per-judge location and scale ----------------------
    judge_stats: dict[str, dict[str, float]] = {}
    for judge_id, vals in by_judge.items():
        n = float(len(vals))
        raw_mean = statistics.fmean(vals)
        raw_sd = _population_sd(vals)
        shrunk_mean = (n * raw_mean + k_shrink * pooled_mean) / (n + k_shrink)
        shrunk_sd = (n * raw_sd + k_shrink * pooled_sd) / (n + k_shrink)
        # pooled_sd == 0 only if every ballot in the event is identical, in
        # which case there is nothing to normalise and the factor is 1.
        scale = (pooled_sd / shrunk_sd) if shrunk_sd > 0 else 1.0
        judge_stats[judge_id] = {
            "n": n,
            "raw_mean": raw_mean,
            "raw_sd": raw_sd,
            "shrunk_mean": shrunk_mean,
            "shrunk_sd": shrunk_sd,
            "scale": scale,
        }

    def scale_corrected(o: Observation) -> float:
        s = judge_stats[o.judge_id]
        return pooled_mean + (o.value - s["shrunk_mean"]) * s["scale"]

    corrected = {(o.judge_id, o.project_id): scale_corrected(o) for o in obs}

    # --- method 1: raw weighted mean ----------------------------------------
    raw_by_project: dict[str, list[float]] = defaultdict(list)
    for o in obs:
        raw_by_project[o.project_id].append(o.value)

    # --- method 2: shrunken z, i.e. stage 1 averaged per project ------------
    z_by_project: dict[str, list[float]] = defaultdict(list)
    for o in obs:
        z_by_project[o.project_id].append(corrected[(o.judge_id, o.project_id)])

    # --- method 3: ridge-penalised additive model on the corrected values ---
    residual = {key: value - pooled_mean for key, value in corrected.items()}
    obs_by_project: dict[str, list[str]] = defaultdict(list)
    obs_by_judge: dict[str, list[str]] = defaultdict(list)
    for o in obs:
        obs_by_project[o.project_id].append(o.judge_id)
        obs_by_judge[o.judge_id].append(o.project_id)

    project_effect = {pid: 0.0 for pid in obs_by_project}
    judge_bias = {jid: 0.0 for jid in obs_by_judge}

    iterations = 0
    converged = False
    for iterations in range(1, MAX_ITER + 1):
        delta = 0.0
        # Project effects given current judge biases.
        for pid, judge_ids in obs_by_project.items():
            total = sum(residual[(jid, pid)] - judge_bias[jid] for jid in judge_ids)
            updated = total / (len(judge_ids) + lambda_project)
            delta = max(delta, abs(updated - project_effect[pid]))
            project_effect[pid] = updated
        # Judge biases given current project effects.
        for jid, project_list in obs_by_judge.items():
            total = sum(residual[(jid, pid)] - project_effect[pid] for pid in project_list)
            updated = total / (len(project_list) + lambda_judge)
            delta = max(delta, abs(updated - judge_bias[jid]))
            judge_bias[jid] = updated
        if delta < TOLERANCE:
            converged = True
            break

    residuals = [
        residual[(o.judge_id, o.project_id)]
        - project_effect[o.project_id]
        - judge_bias[o.judge_id]
        for o in obs
    ]
    residual_sd = _population_sd(residuals) if len(residuals) > 1 else 0.0

    # --- judge spread, before and after -------------------------------------
    # The dispersion between judges of their average given score. This is the
    # quantity the brief's own figure reports as sigma before and after
    # calibration, and it is the headline evidence that the method does work.
    judge_raw_means = [s["raw_mean"] for s in judge_stats.values()]
    judge_calibrated_means: dict[str, float] = {}
    for jid, project_list in obs_by_judge.items():
        calibrated = [
            corrected[(jid, pid)] - judge_bias[jid] for pid in project_list
        ]
        judge_calibrated_means[jid] = statistics.fmean(calibrated)
    spread_before = _population_sd(judge_raw_means)
    spread_after = _population_sd(list(judge_calibrated_means.values()))

    # --- assemble -----------------------------------------------------------
    projects: list[ProjectResult] = []
    for pid in sorted(project_ids):
        n = len(raw_by_project.get(pid, []))
        if n == 0:
            projects.append(
                ProjectResult(
                    project_id=pid,
                    n_reviews=0,
                    raw=None,
                    shrunken_z=None,
                    additive_ridge=None,
                    std_error=None,
                    low_confidence=True,
                    excluded=pid in excluded,
                )
            )
            continue
        projects.append(
            ProjectResult(
                project_id=pid,
                n_reviews=n,
                raw=round(statistics.fmean(raw_by_project[pid]), 6),
                shrunken_z=round(statistics.fmean(z_by_project[pid]), 6),
                additive_ridge=round(pooled_mean + project_effect[pid], 6),
                std_error=round(residual_sd / math.sqrt(n), 6) if residual_sd else 0.0,
                low_confidence=n < LOW_CONFIDENCE_REVIEWS,
                excluded=pid in excluded,
            )
        )

    judges = []
    for jid in sorted(judge_stats):
        s = judge_stats[jid]
        judges.append(
            JudgeDiagnostic(
                judge_id=jid,
                n_reviews=int(s["n"]),
                raw_mean=round(s["raw_mean"], 6),
                raw_sd=round(s["raw_sd"], 6),
                shrunk_mean=round(s["shrunk_mean"], 6),
                shrunk_sd=round(s["shrunk_sd"], 6),
                scale_factor=round(s["scale"], 6),
                bias=round(judge_bias.get(jid, 0.0), 6),
                calibrated_mean=round(judge_calibrated_means.get(jid, 0.0), 6),
                # A judge whose every criterion was identical. Reported, not
                # silently corrected: an organizer should know.
                is_flat=s["n"] > 1 and s["raw_sd"] == 0.0,
                single_ballot=int(s["n"]) == 1,
            )
        )

    result = NormalizationResult(
        method=method,
        projects=projects,
        judges=judges,
        observations=len(obs),
        judge_spread_before=round(spread_before, 6),
        judge_spread_after=round(spread_after, 6),
        residual_sd=round(residual_sd, 6),
        iterations=iterations,
        converged=converged,
        pooled_mean=round(pooled_mean, 6),
        pooled_sd=round(pooled_sd, 6),
        params={
            "k_shrink": k_shrink,
            "lambda_project": lambda_project,
            "lambda_judge": lambda_judge,
        },
    )
    _assign_ranks(result)
    return result


def _assign_ranks(result: NormalizationResult) -> None:
    """Rank by raw mean and by the selected method, and record the movement."""
    scorable = [p for p in result.projects if p.raw is not None and not p.excluded]

    by_raw = sorted(scorable, key=lambda p: (-(p.raw or 0.0), p.project_id))
    for position, project in enumerate(by_raw, start=1):
        project.rank_raw = position

    by_norm = sorted(
        scorable, key=lambda p: (-(p.score(result.method) or 0.0), p.project_id)
    )
    for position, project in enumerate(by_norm, start=1):
        project.rank_normalized = position
        # Positive delta means the project moved up the table once judge bias
        # was removed.
        project.rank_delta = (project.rank_raw or position) - position


# ------------------------------------------- labelled synthetic recovery ---


SYNTHETIC_SEED = 20260301


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mx = statistics.fmean(xs)
    my = statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def _ranks(values: Sequence[float], *, ids: Sequence[str]) -> list[int]:
    """Competition ranks, high value first. Ties broken by id so they are stable."""
    order = sorted(range(len(values)), key=lambda i: (-values[i], ids[i]))
    ranks = [0] * len(values)
    for position, i in enumerate(order, start=1):
        ranks[i] = position
    return ranks


def _kendall_tau(ranks_a: Sequence[int], ranks_b: Sequence[int]) -> float:
    n = len(ranks_a)
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            da = ranks_a[i] - ranks_a[j]
            db = ranks_b[i] - ranks_b[j]
            product = da * db
            if product > 0:
                conc += 1
            elif product < 0:
                disc += 1
    denom = conc + disc
    return (conc - disc) / denom if denom else 0.0


def labelled_recovery(
    fixtures: dict[str, Any],
    *,
    seed: int = SYNTHETIC_SEED,
    mu: float = 3.5,
    project_sd: float = 0.55,
    judge_sd: float = 0.80,
    noise_sd: float = 0.30,
) -> dict[str, Any]:
    """Fit the estimator on a panel with the fixture's missingness and known truth.

    Cells (judge, project) match fixtures.json exactly. Project effects and
    judge biases are drawn, then observations are generated from
        y_ij = mu + p_i + b_j + e_ij
    clipped to the rubric. Recovery is compared against that planted truth —
    not against the real scores — so a high correlation is a claim that the
    method finds a known effect, not merely that it reduced spread.
    """
    rng = random.Random(seed)
    scores = fixtures.get("scores") or []
    project_ids = sorted({s["project"] for s in scores})
    judge_ids = sorted({s["judge"] for s in scores})

    truth_p = {pid: rng.gauss(0.0, project_sd) for pid in project_ids}
    truth_b = {jid: rng.gauss(0.0, judge_sd) for jid in judge_ids}
    mean_p = statistics.fmean(truth_p.values())
    mean_b = statistics.fmean(truth_b.values())
    truth_p = {k: v - mean_p for k, v in truth_p.items()}
    truth_b = {k: v - mean_b for k, v in truth_b.items()}

    observations: list[Observation] = []
    for score in scores:
        value = (
            mu
            + truth_p[score["project"]]
            + truth_b[score["judge"]]
            + rng.gauss(0.0, noise_sd)
        )
        observations.append(
            Observation(
                judge_id=score["judge"],
                project_id=score["project"],
                value=min(5.0, max(1.0, value)),
            )
        )

    result = compute(observations, method="additive_ridge", all_project_ids=project_ids)

    scored = [p for p in result.projects if p.raw is not None]
    recovered_p = [float(p.additive_ridge) - result.pooled_mean for p in scored]
    planted_p = [truth_p[p.project_id] for p in scored]
    raw_means = [float(p.raw) for p in scored]
    ids = [p.project_id for p in scored]

    bias_by_id = {j.judge_id: j.bias for j in result.judges}
    recovered_b = [bias_by_id[jid] for jid in judge_ids]
    planted_b = [truth_b[jid] for jid in judge_ids]

    tau_raw = _kendall_tau(_ranks(planted_p, ids=ids), _ranks(raw_means, ids=ids))
    tau_fit = _kendall_tau(_ranks(planted_p, ids=ids), _ranks(recovered_p, ids=ids))

    return {
        "seed": seed,
        "mu": mu,
        "project_sd": project_sd,
        "judge_sd": judge_sd,
        "noise_sd": noise_sd,
        "observations": len(observations),
        "projects": len(project_ids),
        "judges": len(judge_ids),
        "pearson_project": round(_pearson(planted_p, recovered_p), 4),
        "pearson_bias": round(_pearson(planted_b, recovered_b), 4),
        "kendall_raw_vs_truth": round(tau_raw, 4),
        "kendall_fit_vs_truth": round(tau_fit, 4),
        "spread_before": result.judge_spread_before,
        "spread_after": result.judge_spread_after,
        "converged": result.converged,
    }


# ------------------------------------------------------------- proof output ---


def _fmt(value: float | None, width: int = 6, places: int = 3) -> str:
    if value is None:
        return "-".rjust(width)
    return f"{value:>{width}.{places}f}"


def build_proof(fixtures: dict[str, Any], *, weights: dict[str, float] | None = None) -> str:
    """Render the normalization proof the bonus challenge asks for.

    "Show the raw scores, the normalized scores, and the ranking change." This
    reads fixtures.json directly and needs no running portal, so a judge can
    reproduce it in one command.
    """
    scores = fixtures.get("scores") or []
    projects = fixtures.get("projects") or []
    judges = {j["id"]: j for j in fixtures.get("judges") or []}
    titles = {p["id"]: p.get("title", p["id"]) for p in projects}

    keys: list[str] = []
    for score in scores:
        for key in (score.get("criteria") or {}):
            if key not in keys:
                keys.append(key)
    weights = weights or {key: 1.0 for key in keys}

    observations = [
        Observation(
            judge_id=score["judge"],
            project_id=score["project"],
            value=weighted_value(score.get("criteria") or {}, weights),
        )
        for score in scores
    ]

    # The duplicate pair is detected the same way seed.detect_duplicates does:
    # same team, same normalised title. The later submission is excluded from
    # the ranking and kept in the calibration data.
    seen: dict[tuple[str, str], str] = {}
    duplicates: set[str] = set()
    for project in sorted(projects, key=lambda p: (p.get("submitted_at") or "", p["id"])):
        fingerprint = (project.get("team", ""), " ".join(project.get("title", "").lower().split()))
        if fingerprint in seen:
            duplicates.add(project["id"])
        else:
            seen[fingerprint] = project["id"]

    result = compute(
        observations,
        method="additive_ridge",
        all_project_ids=[p["id"] for p in projects],
        excluded_project_ids=duplicates,
    )

    out: list[str] = []
    w = out.append
    w("DOGFOOD 2026 -- cross-judge normalization proof")
    w("=" * 78)
    w("")
    w("The brief site's FIG. 03 used illustrative numbers (sigma 0.94 -> 0.31).")
    w("Every figure below is computed from fixtures.json. Raw between-judge")
    w("sigma is the population stdev of per-judge means (~0.41; sample stdev")
    w("~0.42). Build against those values, not the illustration.")
    w("")
    w(f"observations        {result.observations}")
    w(f"projects            {len(result.projects)}"
      f"  ({len(duplicates)} excluded from ranking as duplicates)")
    w(f"judges              {len(result.judges)}")
    w(f"rubric weights      {json.dumps(weights, sort_keys=True)}")
    w(f"pooled mean / sd    {result.pooled_mean:.4f} / {result.pooled_sd:.4f}")
    w(f"model               y_ij = mu + p_i + b_j, ridge ALS, "
      f"lambda_p={result.params['lambda_project']}, lambda_b={result.params['lambda_judge']}, "
      f"k={result.params['k_shrink']}")
    w(f"convergence         {result.iterations} iterations, "
      f"converged={result.converged}, residual sd={result.residual_sd:.4f}")
    w("")
    w("BETWEEN-JUDGE SPREAD (the dispersion of judge average scores)")
    w(f"  raw, uncalibrated        sigma = {result.judge_spread_before:.4f}")
    w(f"  after calibration        sigma = {result.judge_spread_after:.4f}")
    reduction = (
        100.0 * (1 - result.judge_spread_after / result.judge_spread_before)
        if result.judge_spread_before
        else 0.0
    )
    w(f"  reduction                {reduction:.1f}%")
    w("")
    w("PER-JUDGE DIAGNOSTICS")
    w("  judge     n   mean     sd   sd~    scale    bias   cal.mean  note")
    w("  " + "-" * 74)
    for j in sorted(result.judges, key=lambda d: -d.raw_mean):
        note = []
        if j.is_flat:
            note.append("FLAT: zero variance, no discriminative weight")
        if j.single_ballot:
            identified = 1.0 / (1.0 + result.params["lambda_judge"])
            note.append(
                f"single ballot: only {identified:.0%} of the residual is "
                f"attributed to bias"
            )
        name = judges.get(j.judge_id, {}).get("name", "")
        w(
            f"  {j.judge_id:<9} {j.n_reviews:>2} {_fmt(j.raw_mean)} "
            f"{_fmt(j.raw_sd, 6, 3)} {_fmt(j.shrunk_sd, 5, 2)} "
            f"{_fmt(j.scale_factor, 7, 3)} {_fmt(j.bias, 7, 3)} "
            f"{_fmt(j.calibrated_mean, 9, 3)}  {'; '.join(note) or name}"
        )
    w("")
    w("PROJECT SCORES: raw -> normalized, with rank movement")
    w("  project   title                 n   raw    z~     norm    se    rank  ->  rank   d")
    w("  " + "-" * 86)
    for p in sorted(
        (p for p in result.projects if not p.excluded),
        key=lambda p: p.rank_normalized or 10**6,
    ):
        flag = " !" if p.low_confidence else "  "
        w(
            f"  {p.project_id:<9} {titles.get(p.project_id, '')[:20]:<20} "
            f"{p.n_reviews:>2}{flag}{_fmt(p.raw, 6, 2)} {_fmt(p.shrunken_z, 6, 2)} "
            f"{_fmt(p.additive_ridge, 7, 3)} {_fmt(p.std_error, 6, 3)} "
            f"{(p.rank_raw or 0):>5}  ->  {(p.rank_normalized or 0):>4} "
            f"{(p.rank_delta or 0):>+4}"
        )
    w("")
    w("  ! = fewer than 3 reviews, reported but flagged low confidence")
    w("")
    excluded_rows = [p for p in result.projects if p.excluded]
    if excluded_rows:
        w("EXCLUDED FROM RANKING (duplicate submissions)")
        for p in excluded_rows:
            w(
                f"  {p.project_id:<9} {titles.get(p.project_id, '')[:20]:<20} "
                f"n={p.n_reviews}  raw={_fmt(p.raw, 5, 2)}  "
                f"norm={_fmt(p.additive_ridge, 6, 3)}   "
                f"ballots retained for judge calibration"
            )
        w("")
    movers = sorted(
        (p for p in result.projects if not p.excluded and p.rank_delta),
        key=lambda p: -abs(p.rank_delta or 0),
    )[:8]
    w("LARGEST RANK MOVEMENTS")
    for p in movers:
        direction = "up" if (p.rank_delta or 0) > 0 else "down"
        w(
            f"  {(p.rank_delta or 0):>+3} {direction:<4} {p.project_id:<9} "
            f"{titles.get(p.project_id, '')[:24]:<24} "
            f"raw rank {p.rank_raw} -> {p.rank_normalized}"
        )
    w("")

    sim = labelled_recovery(fixtures)
    w("LABELLED SYNTHETIC PANEL (validation; not a substitute for the fixture)")
    w("-" * 78)
    w("Same (judge, project) cells as fixtures.json. Scores are generated from")
    w("known project effects p_i, known judge biases b_j, and Gaussian noise:")
    w(f"  y_ij = {sim['mu']} + p_i + b_j + e_ij,  "
      f"p~N(0,{sim['project_sd']}), b~N(0,{sim['judge_sd']}), "
      f"e~N(0,{sim['noise_sd']})")
    w(f"  seed {sim['seed']}; clipped to the 1-5 rubric; "
      f"{sim['observations']} cells, {sim['projects']} projects, "
      f"{sim['judges']} judges")
    w("")
    w("  recovery vs planted truth")
    w(f"    Pearson(p_i, recovered project effect)   {sim['pearson_project']:+.4f}")
    w(f"    Pearson(b_j, recovered judge bias)       {sim['pearson_bias']:+.4f}")
    w(f"    Kendall tau, raw means vs true ranking   {sim['kendall_raw_vs_truth']:+.4f}")
    w(f"    Kendall tau, calibrated vs true ranking  {sim['kendall_fit_vs_truth']:+.4f}")
    w(f"    between-judge sigma  {sim['spread_before']:.4f} -> {sim['spread_after']:.4f}"
      f"  converged={sim['converged']}")
    w("")
    if sim["kendall_fit_vs_truth"] > sim["kendall_raw_vs_truth"]:
        w("  Calibrated ranks match the planted project ranking more closely")
        w("  than raw means do: the estimator recovers a known effect on this")
        w("  missingness pattern, not only a smaller judge spread.")
    else:
        w("  On this draw, calibration did not beat raw means on Kendall tau.")
        w("  Fixture analysis above is the primary claim.")
    w("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m dogfood.normalize",
        description="Cross-judge normalization, and the proof of it on the fixture data.",
    )
    parser.add_argument("--proof", action="store_true", help="print the normalization proof")
    parser.add_argument("--fixtures", default=None, help="path to fixtures.json")
    parser.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = parser.parse_args(argv)

    from .config import settings

    path = Path(args.fixtures) if args.fixtures else settings.fixtures_path
    if not path.is_file():
        print(f"fixtures not found: {path}", file=sys.stderr)
        return 2
    fixtures = json.loads(path.read_text(encoding="utf-8"))

    if args.json:
        scores = fixtures.get("scores") or []
        keys = sorted({k for s in scores for k in (s.get("criteria") or {})})
        weights = {k: 1.0 for k in keys}
        observations = [
            Observation(s["judge"], s["project"], weighted_value(s.get("criteria") or {}, weights))
            for s in scores
        ]
        result = compute(
            observations, all_project_ids=[p["id"] for p in fixtures.get("projects") or []]
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    print(build_proof(fixtures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
