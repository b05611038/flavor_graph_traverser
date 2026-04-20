"""
Statistical tests for the paper.

Why these tests
---------------
The raw score tables (Table 1-2) show that tool access generally *hurts*
performance, but we need statistical tests to distinguish real effects from
noise introduced by question-level variance, scoring granularity, and the
unequal number of questions per task type.

Wilcoxon signed-rank (per model, per task type)
    Non-parametric paired test.  Each question serves as its own control
    (no_tool vs. tool), so the test accounts for question difficulty.
    Bonferroni-corrected across 11 models or 9 task types.  Rank-biserial
    correlation r is reported as effect size (more appropriate than Cohen's
    d for non-normal paired differences).

McNemar's test (binary questions: A2, A3, E1, E2, E3)
    Tests whether the *direction* of flips is asymmetric — i.e., whether
    more questions flip from correct→wrong than wrong→correct when tools
    are added.  Only applicable to task types with strict 0/1 scoring.

Inter-judge agreement (F-category, 3 judges x 15 questions x 11 models x 2
conditions = 330 items)
    The F task type uses subjective 0-5 rubric scoring by three LLM judges
    (Claude Opus 4.6, Gemini 3.1 Pro, GPT-5.4 Pro). Since every other task
    type uses deterministic scoring, we need to show the subjective scores
    are reliable. We report:
      - Krippendorff's alpha (interval metric): chance-corrected agreement.
      - ICC(3,k) (two-way mixed, average measures): agreement treating
        judges as fixed effects, items as random, averaging over raters.
      - Pairwise quadratic-weighted Cohen's kappa (3 pairs): identifies
        which judge pair diverges most; quadratic weighting penalises
        larger disagreements more than smaller ones.
    Rank-biserial r (signed) is reported alongside Wilcoxon; a positive r
    means tool helped, negative means tool hurt.

Bootstrap CIs (stratified by task type)
    Non-parametric 95% confidence intervals on macro, micro, and Δ per
    model.  Stratified resampling (within each task type, with replacement)
    preserves the task-type balance implied by the macro score so the CI
    reflects the same weighting scheme reported in Table 1.  Also computes
    CI on pooled Δ per task type.  Reviewers routinely ask for CIs alongside
    point estimates; these bands also make visually-close models easy to
    distinguish as statistically separable or not.

Kruskal-Wallis (between-group test on Δ)
    Answers: does tool harm differ between model groups (Closed-source,
    Thinking-token, Open-source)?  Non-parametric analogue of one-way
    ANOVA on per-(model, question) Δ values.  Followed by pairwise
    Mann-Whitney U (Bonferroni-corrected) to locate the difference.
    η² is reported as a scale-invariant effect size.

FDR correction (Benjamini-Hochberg)
    Reported alongside Bonferroni in the per-model and per-task Wilcoxon
    tables.  Bonferroni controls family-wise error rate and is
    conservative; BH-FDR controls expected false-discovery rate and is
    standard in modern multiple-testing contexts.  Reporting both lets
    readers pick the regime that matches their preferred error criterion.

Usage:
    python scripts/analysis/statistical_tests.py
    python scripts/analysis/statistical_tests.py --output-dir results/analysis
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
from scipy import stats
from sklearn.metrics import cohen_kappa_score
from scripts.analysis.load_data import (
    load_all_evaluations, get_paired_scores,
    MODEL_ORDER, MODEL_SHORT_NAMES, MODEL_TO_GROUP, MODEL_GROUPS,
    TASK_TYPE_ORDER, BINARY_TYPES, JUDGE_MODELS,
)


# ---------------------------------------------------------------------------
# Shared helpers: bootstrap CI + BH-FDR
# ---------------------------------------------------------------------------

N_BOOT_DEFAULT = 5000
BOOT_SEED = 42


def _json_safe(obj):
    """Recursively convert NaN → None so json.dump(..., allow_nan=False) succeeds.

    Bare ``NaN`` is a JSON extension (not strict-spec) and trips external
    parsers. This scrub keeps the rest of the structure untouched; numpy
    scalars are handled separately by json's ``default=str`` fallback.
    """
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def _bh_fdr(pvalues, alpha=0.05):
    """Benjamini-Hochberg FDR correction.

    Returns (adjusted_pvalues, reject_mask). NaN p-values are preserved and
    never rejected. Adjusted p-values are monotone: for sorted raw p-values
    p_(1) <= ... <= p_(m), adj_(i) = min_{j >= i} (m / j) * p_(j), clipped
    to [0, 1].
    """
    p = np.asarray(pvalues, dtype=float)
    mask = ~np.isnan(p)
    adjusted = np.full_like(p, np.nan, dtype=float)

    if mask.sum() == 0:
        return adjusted, np.zeros_like(p, dtype=bool)

    p_valid = p[mask]
    m = len(p_valid)
    order = np.argsort(p_valid)
    ranked = p_valid[order]
    adj = ranked * m / (np.arange(1, m + 1))
    # Enforce monotonicity from the largest p-value down
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)

    unsort = np.empty_like(adj)
    unsort[order] = adj
    adjusted[mask] = unsort

    reject = np.zeros_like(p, dtype=bool)
    reject[mask] = adjusted[mask] < alpha
    return adjusted, reject


def _stratified_bootstrap_ci(values, strata, agg="mean",
                             n_boot=N_BOOT_DEFAULT, ci=0.95, seed=BOOT_SEED):
    """Stratified bootstrap CI.

    Resamples indices within each stratum with replacement (preserving per-
    stratum sample sizes), then aggregates. ``agg="mean"`` pools all
    resampled values (matches micro score); ``agg="macro"`` averages per-
    stratum means (matches macro score, equal weight per task type).

    Returns (point_estimate, ci_lo, ci_hi). The point estimate is the mean
    of the bootstrap distribution (not the observed statistic) — close to
    the observed but smoothed over resampling noise.
    """
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    strata = np.asarray(strata)

    stratum_indices = {s: np.where(strata == s)[0] for s in np.unique(strata)}
    boot = np.empty(n_boot)

    for b in range(n_boot):
        if agg == "macro":
            task_means = []
            for idx in stratum_indices.values():
                resample = rng.choice(idx, size=len(idx), replace=True)
                task_means.append(values[resample].mean())
            boot[b] = np.mean(task_means)
        else:  # mean
            pooled = []
            for idx in stratum_indices.values():
                resample = rng.choice(idx, size=len(idx), replace=True)
                pooled.append(values[resample])
            boot[b] = np.concatenate(pooled).mean()

    alpha = (1 - ci) / 2
    lo = float(np.percentile(boot, 100 * alpha))
    hi = float(np.percentile(boot, 100 * (1 - alpha)))
    return float(boot.mean()), lo, hi


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank test
# ---------------------------------------------------------------------------

def wilcoxon_per_model(df, n_boot=N_BOOT_DEFAULT):
    """Paired Wilcoxon signed-rank test per model (no_tool vs tool).

    Each question serves as its own control (paired design). Tests whether
    the median difference between conditions is significantly non-zero.
    Bonferroni-corrected across 11 models (alpha = 0.05/11); BH-FDR is
    also reported as a less conservative alternative. Bootstrap 95% CI on
    mean Δ is stratified by task type (resample questions within each task
    type to preserve the 9-task balance).
    """
    paired = get_paired_scores(df)
    n_models = len(MODEL_ORDER)
    alpha_bonferroni = 0.05 / n_models

    results = []
    for model in MODEL_ORDER:
        sub = paired[paired["model"] == model]
        nt = sub["score_no_tool"].values
        t = sub["score_tool"].values
        diff = t - nt
        # Stratify by the dimension not being tested: per-model rows
        # stratify by task_type to keep 9-task balance within each resample.
        task_strata = sub["task_type"].values

        # Bootstrap CI on mean Δ (stratified by task type)
        if len(diff) > 0:
            _, delta_ci_lo, delta_ci_hi = _stratified_bootstrap_ci(
                diff, task_strata, agg="mean", n_boot=n_boot,
            )
        else:
            delta_ci_lo = delta_ci_hi = np.nan

        # Remove ties (diff == 0) for Wilcoxon
        nonzero = diff[diff != 0]
        if len(nonzero) < 10:
            results.append({
                "model": MODEL_SHORT_NAMES.get(model, model),
                "n_pairs": len(diff),
                "n_nonzero": len(nonzero),
                "mean_delta": np.mean(diff) if len(diff) else np.nan,
                "delta_ci_lo": delta_ci_lo,
                "delta_ci_hi": delta_ci_hi,
                "W": np.nan, "p_value": np.nan,
                "r_effect": np.nan,
                "significant_bonferroni": False,
            })
            continue

        stat, p = stats.wilcoxon(nt, t, alternative="two-sided")

        # Rank-biserial correlation as effect size: r = (W+ - W-) / (W+ + W-)
        # scipy returns W = min(W+, W-) which loses sign; compute W+ explicitly
        # so the sign matches the direction of (tool - no_tool).
        n = len(nonzero)
        ranks = stats.rankdata(np.abs(nonzero))
        w_plus = np.sum(ranks[nonzero > 0])
        total = n * (n + 1) / 2
        r = (2 * w_plus - total) / total

        results.append({
            "model": MODEL_SHORT_NAMES.get(model, model),
            "n_pairs": len(diff),
            "n_nonzero": len(nonzero),
            "mean_delta": np.mean(diff),
            "delta_ci_lo": delta_ci_lo,
            "delta_ci_hi": delta_ci_hi,
            "W": stat,
            "p_value": p,
            "r_effect": r,
            "significant_bonferroni": p < alpha_bonferroni,
        })

    out = pd.DataFrame(results)
    # BH-FDR across models
    p_fdr, reject_fdr = _bh_fdr(out["p_value"].values, alpha=0.05)
    out["p_fdr"] = p_fdr
    out["significant_fdr"] = reject_fdr
    return out


def wilcoxon_per_task(df, n_boot=N_BOOT_DEFAULT):
    """Paired Wilcoxon signed-rank test per task type (pooling all models).

    Pools all 11 models into a single test per task type. Trades off
    per-model resolution for statistical power — useful for detecting
    which task types have significant tool effects overall.
    Bonferroni-corrected across 9 task types (alpha = 0.05/9); BH-FDR is
    also reported. Bootstrap 95% CI on mean Δ is stratified by model
    (resample pairs within each model to preserve the 11-model balance).
    """
    paired = get_paired_scores(df)
    n_tasks = len(TASK_TYPE_ORDER)
    alpha_bonferroni = 0.05 / n_tasks

    results = []
    for task in TASK_TYPE_ORDER:
        sub = paired[paired["task_type"] == task]
        nt = sub["score_no_tool"].values
        t = sub["score_tool"].values
        diff = t - nt
        # Stratify by the dimension not being tested: per-task rows
        # stratify by model to keep the 11-model balance within each resample.
        model_strata = sub["model"].values

        if len(diff) > 0:
            _, delta_ci_lo, delta_ci_hi = _stratified_bootstrap_ci(
                diff, model_strata, agg="mean", n_boot=n_boot,
            )
        else:
            delta_ci_lo = delta_ci_hi = np.nan

        nonzero = diff[diff != 0]
        if len(nonzero) < 10:
            results.append({
                "task_type": task,
                "n_pairs": len(diff),
                "n_nonzero": len(nonzero),
                "mean_delta": np.mean(diff) if len(diff) else np.nan,
                "delta_ci_lo": delta_ci_lo,
                "delta_ci_hi": delta_ci_hi,
                "W": np.nan, "p_value": np.nan,
                "r_effect": np.nan,
                "significant_bonferroni": False,
            })
            continue

        stat, p = stats.wilcoxon(nt, t, alternative="two-sided")
        n = len(nonzero)
        ranks = stats.rankdata(np.abs(nonzero))
        w_plus = np.sum(ranks[nonzero > 0])
        total = n * (n + 1) / 2
        r = (2 * w_plus - total) / total

        results.append({
            "task_type": task,
            "n_pairs": len(diff),
            "n_nonzero": len(nonzero),
            "mean_delta": np.mean(diff),
            "delta_ci_lo": delta_ci_lo,
            "delta_ci_hi": delta_ci_hi,
            "W": stat,
            "p_value": p,
            "r_effect": r,
            "significant_bonferroni": p < alpha_bonferroni,
        })

    out = pd.DataFrame(results)
    p_fdr, reject_fdr = _bh_fdr(out["p_value"].values, alpha=0.05)
    out["p_fdr"] = p_fdr
    out["significant_fdr"] = reject_fdr
    return out


# ---------------------------------------------------------------------------
# McNemar's test (binary questions only)
# ---------------------------------------------------------------------------

def mcnemar_per_model(df):
    """McNemar's test for binary (single-choice) questions per model.

    Focuses on discordant pairs: questions that flip between correct and
    wrong across conditions. Tests whether flips are asymmetric (more
    correct->wrong than wrong->correct, or vice versa).

    Implementation: chi-squared approximation with continuity correction
    (not exact binomial). Rows with fewer than 5 discordant pairs are
    reported as N/A since the test is unreliable at that count.
    Applicable only to task types with strict 0/1 scoring (A2/A3/E1/E2/E3).
    """
    binary_df = df[df["task_type"].isin(BINARY_TYPES)].copy()
    paired = get_paired_scores(binary_df)

    results = []
    for model in MODEL_ORDER:
        sub = paired[paired["model"] == model]

        # Convert scores to correct/wrong (binary: score is 0 or 1)
        nt_correct = (sub["score_no_tool"] == 1.0).values
        t_correct = (sub["score_tool"] == 1.0).values

        # McNemar contingency: discordant pairs
        b = np.sum(nt_correct & ~t_correct)  # correct_no_tool, wrong_tool
        c = np.sum(~nt_correct & t_correct)  # wrong_no_tool, correct_tool
        a = np.sum(nt_correct & t_correct)   # both correct
        d = np.sum(~nt_correct & ~t_correct) # both wrong

        n_discord = b + c
        if n_discord < 5:
            # Too few discordant pairs for valid test
            results.append({
                "model": MODEL_SHORT_NAMES.get(model, model),
                "both_correct": int(a), "both_wrong": int(d),
                "nt_only": int(b), "tool_only": int(c),
                "chi2": np.nan, "p_value": np.nan,
                "direction": "N/A",
            })
            continue

        # McNemar with continuity correction
        chi2 = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) > 0 else 0
        p = 1 - stats.chi2.cdf(chi2, df=1)

        direction = "tool hurts" if b > c else "tool helps" if c > b else "neutral"

        results.append({
            "model": MODEL_SHORT_NAMES.get(model, model),
            "both_correct": int(a), "both_wrong": int(d),
            "nt_only": int(b), "tool_only": int(c),
            "chi2": chi2, "p_value": p,
            "direction": direction,
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# McNemar's test per task type (binary questions only)
# ---------------------------------------------------------------------------

def mcnemar_per_task(df):
    """McNemar's test for binary questions per task type (pooling all models).

    Pools all 11 models per task type to maximise statistical power for
    detecting task-level asymmetry in flip direction. This directly tests
    whether tools systematically help or hurt on specific binary task types,
    providing statistical backing for the observed positive-Δ on A3 and E3.

    Bonferroni correction is applied across the 5 binary task types
    (alpha = 0.05/5 = 0.01); BH-FDR is also reported.
    """
    binary_df = df[df["task_type"].isin(BINARY_TYPES)].copy()
    paired = get_paired_scores(binary_df)

    results = []
    task_order = [t for t in TASK_TYPE_ORDER if t in BINARY_TYPES]
    n_tests = len(task_order)

    for task in task_order:
        sub = paired[paired["task_type"] == task]

        nt_correct = (sub["score_no_tool"] == 1.0).values
        t_correct = (sub["score_tool"] == 1.0).values

        b = np.sum(nt_correct & ~t_correct)   # correct_no_tool, wrong_tool
        c = np.sum(~nt_correct & t_correct)   # wrong_no_tool, correct_tool
        a = np.sum(nt_correct & t_correct)    # both correct
        d = np.sum(~nt_correct & ~t_correct)  # both wrong

        n_discord = b + c
        if n_discord < 5:
            results.append({
                "task_type": task, "n_pairs": len(sub),
                "both_correct": int(a), "both_wrong": int(d),
                "nt_only": int(b), "tool_only": int(c),
                "chi2": np.nan, "p_value": np.nan,
                "p_bonferroni": np.nan, "significant_bonferroni": False,
                "direction": "N/A",
            })
            continue

        chi2 = (abs(b - c) - 1) ** 2 / (b + c)
        p = 1 - stats.chi2.cdf(chi2, df=1)
        p_bonf = float(min(p * n_tests, 1.0)) if not np.isnan(p) else np.nan
        direction = "tool hurts" if b > c else "tool helps" if c > b else "neutral"

        results.append({
            "task_type": task, "n_pairs": len(sub),
            "both_correct": int(a), "both_wrong": int(d),
            "nt_only": int(b), "tool_only": int(c),
            "chi2": chi2, "p_value": p,
            "p_bonferroni": p_bonf,
            "significant_bonferroni": p_bonf < 0.05,
            "direction": direction,
        })

    out = pd.DataFrame(results)
    p_fdr, reject_fdr = _bh_fdr(out["p_value"].values, alpha=0.05)
    out["p_fdr"] = p_fdr
    out["significant_fdr"] = reject_fdr
    return out


# ---------------------------------------------------------------------------
# Inter-judge agreement (F-category)
# ---------------------------------------------------------------------------

def _krippendorff_alpha_interval(ratings_matrix):
    """Compute Krippendorff's alpha with interval metric (squared differences).

    ratings_matrix: shape (n_items, n_raters), values 0-5, NaN for missing.

    Caveats:
    - Uses interval (squared-difference) metric. For a 6-point scale (0-5),
      interval and ordinal metrics yield near-identical results.
    - Simplified per-pair-mean implementation: valid only when every item
      has the same number of raters (true in this dataset: all 3 judges
      rate every F-category item). Does NOT use the full coincidence matrix
      that would normalize correctly under variable rater counts.
    """
    n_items, n_raters = ratings_matrix.shape

    # Collect all non-NaN pairs within each item
    pairs = []
    for i in range(n_items):
        vals = ratings_matrix[i][~np.isnan(ratings_matrix[i])]
        if len(vals) < 2:
            continue
        for a in range(len(vals)):
            for b in range(a + 1, len(vals)):
                pairs.append((vals[a], vals[b]))

    if not pairs:
        return np.nan

    # Observed disagreement
    pairs = np.array(pairs)
    d_obs = np.mean((pairs[:, 0] - pairs[:, 1]) ** 2)

    # Expected disagreement (marginal distribution)
    all_vals = ratings_matrix[~np.isnan(ratings_matrix)]
    n_total = len(all_vals)
    d_exp = np.var(all_vals) * (n_total / (n_total - 1)) if n_total > 1 else 0

    if d_exp == 0:
        return 1.0

    alpha = 1 - d_obs / d_exp
    return alpha


def inter_judge_agreement(df):
    """Compute inter-judge agreement metrics for F-category items.

    F-type questions are scored by 3 LLM judges on a 0-5 rubric. We need
    to show that judges agree well enough to trust the mean score as a
    reliable measure, since all other task types use deterministic scoring.

    Returns a dict with:
      - n_items: number of items with all 3 judge scores.
      - mean_/std_{judge}: per-judge score distribution (systematic bias
        check).
      - krippendorff_alpha: chance-corrected agreement (interval metric).
      - icc_3k: intraclass correlation, two-way mixed model.
      - kappa_{pair}: quadratic-weighted Cohen's kappa for 3 judge pairs.
      - pct_exact / pct_off_by_1 / pct_off_by_2 / pct_off_by_3plus:
        distribution of max pairwise disagreement per item.
    """
    f_df = df[df["task_type"] == "F"].copy()

    # Need both conditions, all models
    judge_cols = ["judge_score_opus", "judge_score_gemini", "judge_score_gpt"]
    judge_names = ["Opus 4.6", "Gemini 3.1 Pro", "GPT-5.4 Pro"]

    # Filter to rows with all 3 judges
    has_all = f_df[judge_cols].notna().all(axis=1)
    f_scored = f_df[has_all].copy()

    if len(f_scored) == 0:
        print("WARNING: No F-category items with all 3 judge scores found.")
        return {}

    ratings = f_scored[judge_cols].values.astype(float)
    n_items = len(ratings)

    results = {"n_items": n_items}

    # Per-judge statistics
    for i, (col, name) in enumerate(zip(judge_cols, judge_names)):
        vals = ratings[:, i]
        results[f"mean_{name}"] = float(np.mean(vals))
        results[f"std_{name}"] = float(np.std(vals))

    # Krippendorff's alpha
    results["krippendorff_alpha"] = float(_krippendorff_alpha_interval(ratings))

    # Pairwise weighted Cohen's kappa
    pairs = [(0, 1, "Opus-Gemini"), (0, 2, "Opus-GPT"), (1, 2, "Gemini-GPT")]
    for i, j, pair_name in pairs:
        kappa = cohen_kappa_score(
            ratings[:, i].astype(int),
            ratings[:, j].astype(int),
            weights="quadratic",
        )
        results[f"kappa_{pair_name}"] = float(kappa)

    # Agreement distribution
    max_diff = np.max(ratings, axis=1) - np.min(ratings, axis=1)
    results["pct_exact"] = float(np.mean(max_diff == 0))
    results["pct_off_by_1"] = float(np.mean(max_diff == 1))
    results["pct_off_by_2"] = float(np.mean(max_diff == 2))
    results["pct_off_by_3plus"] = float(np.mean(max_diff >= 3))

    # ICC(3,k) — two-way mixed, average measures
    # Using manual computation: ICC = (MSR - MSE) / (MSR + (k-1)*MSE)
    k = 3  # number of raters
    item_means = np.mean(ratings, axis=1)
    grand_mean = np.mean(ratings)
    rater_means = np.mean(ratings, axis=0)

    ss_rows = k * np.sum((item_means - grand_mean) ** 2)
    ss_cols = n_items * np.sum((rater_means - grand_mean) ** 2)
    ss_total = np.sum((ratings - grand_mean) ** 2)
    ss_error = ss_total - ss_rows - ss_cols

    ms_rows = ss_rows / (n_items - 1) if n_items > 1 else 0
    ms_error = ss_error / ((n_items - 1) * (k - 1)) if (n_items > 1 and k > 1) else 0

    if (ms_rows + (k - 1) * ms_error) > 0:
        icc = (ms_rows - ms_error) / (ms_rows + (k - 1) * ms_error)
    else:
        icc = 0.0
    results["icc_3k"] = float(icc)

    return results


# ---------------------------------------------------------------------------
# Bootstrap CIs on macro / micro / Δ per model
# ---------------------------------------------------------------------------

def bootstrap_scores(df, n_boot=N_BOOT_DEFAULT, seed=BOOT_SEED):
    """Bootstrap 95% CIs for macro / micro / Δ per model.

    Stratified by task type: within each bootstrap iteration we resample
    questions within each of the 9 task types (with replacement, preserving
    per-task sample size), then compute:
      - macro score = mean of per-task means (equal weight per task).
      - micro score = mean of all resampled scores (weights by task size).
      - Δ = tool minus no_tool (same pairing).

    Reporting both macro and micro CIs matches Table 1's point estimates
    and lets readers see how much the equal-weight vs. question-weighted
    choice moves the interval. Each model gets an independent RNG stream
    spawned from the same seed, so per-model CIs do not depend on model
    iteration order and remain reproducible if the model list is filtered.
    """
    seed_seq = np.random.SeedSequence(seed)
    child_seeds = seed_seq.spawn(len(MODEL_ORDER))
    paired_all = get_paired_scores(df)

    results = []
    for model_idx, model in enumerate(MODEL_ORDER):
        rng = np.random.default_rng(child_seeds[model_idx])
        paired_m = paired_all[paired_all["model"] == model].reset_index(drop=True)
        nt_arr = paired_m["score_no_tool"].values
        t_arr = paired_m["score_tool"].values
        task_indices = paired_m.groupby("task_type").indices  # task -> row indices

        macro_nt = np.empty(n_boot)
        macro_t = np.empty(n_boot)
        micro_nt = np.empty(n_boot)
        micro_t = np.empty(n_boot)

        for b in range(n_boot):
            task_means_nt = []
            task_means_t = []
            pooled_nt = []
            pooled_t = []
            for idx in task_indices.values():
                resample = rng.choice(idx, size=len(idx), replace=True)
                nt_sample = nt_arr[resample]
                t_sample = t_arr[resample]
                task_means_nt.append(nt_sample.mean())
                task_means_t.append(t_sample.mean())
                pooled_nt.append(nt_sample)
                pooled_t.append(t_sample)
            macro_nt[b] = np.mean(task_means_nt)
            macro_t[b] = np.mean(task_means_t)
            micro_nt[b] = np.concatenate(pooled_nt).mean()
            micro_t[b] = np.concatenate(pooled_t).mean()

        macro_delta = macro_t - macro_nt
        micro_delta = micro_t - micro_nt

        def pct(arr):
            return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))

        m_nt_lo, m_nt_hi = pct(macro_nt)
        m_t_lo, m_t_hi = pct(macro_t)
        md_lo, md_hi = pct(macro_delta)
        mi_nt_lo, mi_nt_hi = pct(micro_nt)
        mi_t_lo, mi_t_hi = pct(micro_t)
        mid_lo, mid_hi = pct(micro_delta)

        results.append({
            "model": MODEL_SHORT_NAMES.get(model, model),
            "model_group": MODEL_TO_GROUP.get(model, "Unknown"),
            "macro_no_tool": float(macro_nt.mean()),
            "macro_no_tool_ci_lo": m_nt_lo,
            "macro_no_tool_ci_hi": m_nt_hi,
            "macro_tool": float(macro_t.mean()),
            "macro_tool_ci_lo": m_t_lo,
            "macro_tool_ci_hi": m_t_hi,
            "macro_delta": float(macro_delta.mean()),
            "macro_delta_ci_lo": md_lo,
            "macro_delta_ci_hi": md_hi,
            "micro_no_tool": float(micro_nt.mean()),
            "micro_no_tool_ci_lo": mi_nt_lo,
            "micro_no_tool_ci_hi": mi_nt_hi,
            "micro_tool": float(micro_t.mean()),
            "micro_tool_ci_lo": mi_t_lo,
            "micro_tool_ci_hi": mi_t_hi,
            "micro_delta": float(micro_delta.mean()),
            "micro_delta_ci_lo": mid_lo,
            "micro_delta_ci_hi": mid_hi,
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Kruskal-Wallis between model groups on Δ
# ---------------------------------------------------------------------------

def kruskal_between_groups(df):
    """Kruskal-Wallis test: do model groups differ in tool Δ?

    Tests whether the distribution of per-(model, question) Δ values
    differs across the three model groups (Closed-source, Thinking-token,
    Open-source). Non-parametric analogue of one-way ANOVA; robust to the
    non-normal, bounded [-1, 1] Δ distribution.

    Effect size: η² = (H − k + 1) / (N − k), where k = number of groups.
    Follow-up pairwise Mann-Whitney U tests (Bonferroni-corrected over the
    three pairs) locate which groups differ. Returns a dict suitable for
    JSON serialisation.
    """
    paired = get_paired_scores(df)
    paired = paired.assign(model_group=paired["model"].map(MODEL_TO_GROUP))

    group_order = ["Closed-source", "Thinking-token", "Open-source"]
    groups = {g: paired.loc[paired["model_group"] == g, "delta"].values for g in group_order}

    h_stat, p = stats.kruskal(*groups.values())

    n_total = sum(len(v) for v in groups.values())
    k = len(groups)
    eta2 = (h_stat - k + 1) / (n_total - k) if n_total > k else np.nan

    result = {
        "H_statistic": float(h_stat),
        "p_value": float(p),
        "eta_squared": float(eta2),
        "n_groups": int(k),
        "n_total": int(n_total),
        "group_sizes": {g: int(len(v)) for g, v in groups.items()},
        "group_means": {g: float(np.mean(v)) for g, v in groups.items()},
        "group_medians": {g: float(np.median(v)) for g, v in groups.items()},
        "significant": bool(p < 0.05),
    }

    # Pairwise Mann-Whitney U with Bonferroni (3 pairs)
    posthoc = []
    pair_indices = [(0, 1), (0, 2), (1, 2)]
    n_pairs = len(pair_indices)
    for i, j in pair_indices:
        g1, g2 = group_order[i], group_order[j]
        u, p_pair = stats.mannwhitneyu(groups[g1], groups[g2], alternative="two-sided")
        p_bonf = float(min(p_pair * n_pairs, 1.0))
        posthoc.append({
            "pair": f"{g1} vs {g2}",
            "U": float(u),
            "p_value": float(p_pair),
            "p_bonferroni": p_bonf,
            "significant_bonferroni": bool(p_bonf < 0.05),
            f"median_{g1}": float(np.median(groups[g1])),
            f"median_{g2}": float(np.median(groups[g2])),
        })
    result["posthoc_mannwhitney"] = posthoc
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run statistical tests")
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--output-dir", default="results/analysis")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_all_evaluations(args.results_dir)

    # --- Wilcoxon per model ---
    print("\n=== Wilcoxon Signed-Rank Test (per model) ===")
    print(f"Bonferroni α = 0.05/{len(MODEL_ORDER)} = {0.05/len(MODEL_ORDER):.4f}  |  FDR α = 0.05 (BH)\n")
    w_model = wilcoxon_per_model(df)
    for _, row in w_model.iterrows():
        flags = ("B" if row["significant_bonferroni"] else "-") + \
                ("F" if row["significant_fdr"] else "-")
        print(f"  {row['model']:<22s} Δ={row['mean_delta']:+.4f} "
              f"[{row['delta_ci_lo']:+.3f},{row['delta_ci_hi']:+.3f}]  "
              f"W={row['W']:8.0f}  p={row['p_value']:.2e}  "
              f"p_fdr={row['p_fdr']:.2e}  r={row['r_effect']:+.3f}  {flags}")
    w_model.to_csv(output_dir / "stats_wilcoxon_per_model.csv", index=False)

    # --- Wilcoxon per task type ---
    print("\n=== Wilcoxon Signed-Rank Test (per task type) ===")
    print(f"Bonferroni α = 0.05/{len(TASK_TYPE_ORDER)} = {0.05/len(TASK_TYPE_ORDER):.4f}  |  FDR α = 0.05 (BH)\n")
    w_task = wilcoxon_per_task(df)
    for _, row in w_task.iterrows():
        flags = ("B" if row["significant_bonferroni"] else "-") + \
                ("F" if row["significant_fdr"] else "-")
        print(f"  {row['task_type']:<6s} Δ={row['mean_delta']:+.4f} "
              f"[{row['delta_ci_lo']:+.3f},{row['delta_ci_hi']:+.3f}]  "
              f"W={row['W']:10.0f}  p={row['p_value']:.2e}  "
              f"p_fdr={row['p_fdr']:.2e}  r={row['r_effect']:+.3f}  "
              f"n={row['n_pairs']:4d}  {flags}")
    w_task.to_csv(output_dir / "stats_wilcoxon_per_task.csv", index=False)

    # --- McNemar per model ---
    print("\n=== McNemar's Test (binary questions, per model) ===")
    print(f"Binary types: {sorted(BINARY_TYPES)}\n")
    mc = mcnemar_per_model(df)
    for _, row in mc.iterrows():
        print(f"  {row['model']:<22s} nt_only={row['nt_only']:3d}  tool_only={row['tool_only']:3d}  "
              f"χ²={row['chi2']:7.2f}  p={row['p_value']:.2e}  {row['direction']}")
    mc.to_csv(output_dir / "stats_mcnemar_per_model.csv", index=False)

    # --- McNemar per task type ---
    print("\n=== McNemar's Test (binary questions, per task type) ===")
    print(f"Bonferroni α = 0.05/{len(BINARY_TYPES)} = {0.05/len(BINARY_TYPES):.3f}  |  FDR α = 0.05 (BH)\n")
    mc_task = mcnemar_per_task(df)
    for _, row in mc_task.iterrows():
        flags = ("B" if row["significant_bonferroni"] else "-") + \
                ("F" if row["significant_fdr"] else "-")
        if pd.isna(row["p_value"]):
            print(f"  {row['task_type']:<6s} n={row['n_pairs']:4d}  "
                  f"nt_only={row['nt_only']:4d}  tool_only={row['tool_only']:4d}  "
                  f"χ²=    N/A  p=       N/A  p_bonf=       N/A  {row['direction']}  {flags}")
        else:
            print(f"  {row['task_type']:<6s} n={row['n_pairs']:4d}  "
                  f"nt_only={row['nt_only']:4d}  tool_only={row['tool_only']:4d}  "
                  f"χ²={row['chi2']:7.2f}  p={row['p_value']:.2e}  "
                  f"p_bonf={row['p_bonferroni']:.2e}  {row['direction']}  {flags}")
    mc_task.to_csv(output_dir / "stats_mcnemar_per_task.csv", index=False)

    # --- Inter-judge agreement ---
    print("\n=== Inter-Judge Agreement (F-category) ===")
    ija = inter_judge_agreement(df)
    if ija:
        print(f"  Items: {ija['n_items']}")
        for name in ["Opus 4.6", "Gemini 3.1 Pro", "GPT-5.4 Pro"]:
            print(f"  {name:<20s} mean={ija[f'mean_{name}']:.2f}  std={ija[f'std_{name}']:.2f}")
        print(f"\n  Krippendorff's α:  {ija['krippendorff_alpha']:.3f}")
        print(f"  ICC(3,k):          {ija['icc_3k']:.3f}")
        for pair in ["Opus-Gemini", "Opus-GPT", "Gemini-GPT"]:
            print(f"  κ ({pair}):  {ija[f'kappa_{pair}']:.3f}")
        print(f"\n  Agreement: {ija['pct_exact']:.1%} exact, "
              f"{ija['pct_off_by_1']:.1%} ±1, "
              f"{ija['pct_off_by_2']:.1%} ±2, "
              f"{ija['pct_off_by_3plus']:.1%} ±3+")

        with open(output_dir / "stats_judge_agreement.json", "w") as f:
            json.dump(ija, f, indent=2)

    # --- Bootstrap CIs per model ---
    print("\n=== Bootstrap 95% CIs per model (stratified by task type) ===")
    boot = bootstrap_scores(df)
    for _, row in boot.iterrows():
        print(f"  {row['model']:<22s} "
              f"macro_Δ={row['macro_delta']:+.4f} "
              f"[{row['macro_delta_ci_lo']:+.3f},{row['macro_delta_ci_hi']:+.3f}]  "
              f"micro_Δ={row['micro_delta']:+.4f} "
              f"[{row['micro_delta_ci_lo']:+.3f},{row['micro_delta_ci_hi']:+.3f}]")
    boot.to_csv(output_dir / "stats_bootstrap_scores.csv", index=False)

    # --- Kruskal-Wallis between model groups ---
    print("\n=== Kruskal-Wallis: Δ distribution across model groups ===")
    kw = kruskal_between_groups(df)
    print(f"  H={kw['H_statistic']:.3f}  p={kw['p_value']:.2e}  "
          f"η²={kw['eta_squared']:.4f}  N={kw['n_total']}  "
          f"{'(significant)' if kw['significant'] else '(not significant)'}")
    for g, m in kw["group_means"].items():
        print(f"    {g:<16s} n={kw['group_sizes'][g]:4d}  "
              f"mean_Δ={m:+.4f}  median_Δ={kw['group_medians'][g]:+.4f}")
    print("  Pairwise Mann-Whitney (Bonferroni over 3 pairs):")
    for ph in kw["posthoc_mannwhitney"]:
        sig = "***" if ph["significant_bonferroni"] else ""
        print(f"    {ph['pair']:<42s} U={ph['U']:10.0f}  "
              f"p={ph['p_value']:.2e}  p_bonf={ph['p_bonferroni']:.2e}  {sig}")
    with open(output_dir / "stats_kruskal_groups.json", "w") as f:
        json.dump(kw, f, indent=2)

    # --- Save all stats to JSON ---
    all_stats = {
        "wilcoxon_per_model": w_model.to_dict(orient="records"),
        "wilcoxon_per_task": w_task.to_dict(orient="records"),
        "mcnemar_per_model": mc.to_dict(orient="records"),
        "mcnemar_per_task": mc_task.to_dict(orient="records"),
        "judge_agreement": ija,
        "bootstrap_scores": boot.to_dict(orient="records"),
        "kruskal_between_groups": kw,
    }
    all_stats = _json_safe(all_stats)
    with open(output_dir / "stats_all.json", "w") as f:
        json.dump(all_stats, f, indent=2, default=str, allow_nan=False)
    print(f"\nAll stats saved to {output_dir / 'stats_all.json'}")


if __name__ == "__main__":
    main()
