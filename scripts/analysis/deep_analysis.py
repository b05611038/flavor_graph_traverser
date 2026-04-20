"""
Deep analysis for the paper.

The tables and statistical tests establish *that* tools hurt performance.
This module investigates *why* and *how*, producing evidence for the
paper's mechanistic claims.

1. Anchoring analysis
   The tool graph (111 SCAA nodes) is a strict subset of the system graph
   used to generate questions.  When a model calls ``validate_descriptors``
   on a correct-but-absent descriptor, the tool returns "invalid".  Models
   treat this as negative evidence and reject the answer — a form of
   anchoring bias.  We correlate the invalid-descriptor ratio with score
   drops per task type and compute a Recovery Index
   (reasoning_calls / val_call_count) to measure whether follow-up
   exploration (get_parent / get_children / get_siblings) mitigates the
   initial anchoring.

2. Prompt-level anchoring
   Some models (notably GPT-5.4) make zero reasoning tool calls
   (``reasoning_calls == 0``) yet still show negative Δ.  The tool-
   condition system prompt contains epistemic framing ("only treat
   confirmed results as positive evidence") that causes the model to
   self-constrain its parametric knowledge.  We quantify this by
   measuring the score-drift rate (fraction of paired items whose
   score changed by more than 0.01 between conditions) for zero-call
   subsets, separated by task type.  For binary tasks this equals the
   answer flip rate; for F1 / judge-scored tasks it captures any score
   movement even if the model's answer is semantically similar.

3. Tool-skip analysis
   Splits tool-condition evaluations into skippers (reasoning_calls = 0)
   vs. users (reasoning_calls > 0) to disentangle prompt-level harm from
   tool-interaction harm.  Caveat: the split is not random — question
   difficulty, task type, and model behaviour all influence whether a
   model chose to call tools, so Δ differences between groups conflate
   self-selection with the prompt / tool effect.

4. Token cost analysis
   Computes per-evaluation cost from API-reported token counts and
   OpenRouter published prices (configs/models.yaml).  The tool condition
   uses substantially more tokens (multi-turn tool calls) for *lower*
   scores — framed as the "cost of degradation" in the paper.

5. Parse error audit
   Documents non-success cases (parse errors, tool errors) and verifies
   they do not change any model's Δ sign when excluded — a robustness
   check for the main results.

6. Vocabulary gap analysis
   Tests the core mechanism: the 111-node tool graph is a strict vocabulary
   subset of real-world flavor space, so ``validate_descriptors`` returns
   "invalid" for virtually every legitimate descriptor in the question set.
   Two empirical tests: (a) NONE-response inflation (6% → 23% under tool
   condition, 81% of tool-NONE answers are wrong), and (b) A1 correct-answer
   vocabulary split — questions where the correct root category IS in the
   tool graph show positive Δ; questions where it is NOT show strongly
   negative Δ.  See docs/memo_vocabulary_gap_anchoring_20260420.md.

Usage:
    python scripts/analysis/deep_analysis.py
    python scripts/analysis/deep_analysis.py --output-dir results/analysis
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scripts.analysis.load_data import (
    load_all_evaluations, get_paired_scores,
    MODEL_ORDER, MODEL_SHORT_NAMES, MODEL_TO_GROUP, TASK_TYPE_ORDER,
)


# ---------------------------------------------------------------------------
# 1. Anchoring analysis
# ---------------------------------------------------------------------------

def anchoring_analysis(df, output_dir):
    """Correlate validate_descriptors invalid rate with score drops.

    The tool graph (111 nodes) is a strict subset of the system graph used
    to generate questions. When models call validate_descriptors on a
    correct descriptor absent from the tool graph, the tool returns
    "invalid". This analysis quantifies how strongly that false-negative
    signal anchors models toward wrong answers.

    Filters to tool-condition rows with at least one validate_descriptors
    call (val_call_count > 0). Rows that used reasoning tools (e.g.
    get_parent) but never validate_descriptors are excluded because the
    invalid-ratio is undefined for them; the excluded count is reported.
    """
    print("\n" + "=" * 60)
    print("1. ANCHORING ANALYSIS (validate_descriptors → score)")
    print("=" * 60)

    tool_df = df[df["condition"] == "tool"].copy()

    # Only rows with at least one validate call
    has_val = tool_df[tool_df["val_call_count"] > 0].copy()
    has_reasoning_no_val = tool_df[(tool_df["reasoning_calls"] > 0) & (tool_df["val_call_count"] == 0)]
    print(f"\nTool-condition rows with validate calls: {len(has_val)}/{len(tool_df)}")
    print(f"  (Excluded: {len(has_reasoning_no_val)} rows used reasoning tools but not validate_descriptors)")

    # Correlation: invalid_ratio vs score
    valid = has_val[has_val["val_invalid_ratio"].notna()]
    if len(valid) > 10:
        r, p = stats.spearmanr(valid["val_invalid_ratio"], valid["score"])
        print(f"Spearman correlation (invalid_ratio vs score): r={r:.3f}, p={p:.2e}")

    # Per task type
    print(f"\n{'Task':<6s} {'n':>5s} {'mean_inv_ratio':>14s} {'mean_score':>11s} {'r_spearman':>11s} {'p':>10s}")
    print("-" * 62)
    task_results = []
    for task in TASK_TYPE_ORDER:
        sub = valid[valid["task_type"] == task]
        if len(sub) < 5:
            continue
        inv = sub["val_invalid_ratio"].mean()
        sc = sub["score"].mean()
        if sub["val_invalid_ratio"].std() > 0 and sub["score"].std() > 0:
            r, p = stats.spearmanr(sub["val_invalid_ratio"], sub["score"])
        else:
            r, p = np.nan, np.nan
        print(f"{task:<6s} {len(sub):5d} {inv:14.3f} {sc:11.3f} {r:11.3f} {p:10.2e}")
        task_results.append({"task_type": task, "n": len(sub),
                             "mean_invalid_ratio": inv, "mean_score": sc,
                             "spearman_r": r, "spearman_p": p})

    pd.DataFrame(task_results).to_csv(
        output_dir / "deep_anchoring_by_task.csv", index=False
    )

    # Recovery Index: reasoning_calls / validation_calls
    has_val["recovery_index"] = has_val["reasoning_calls"] / has_val["val_call_count"]
    print(f"\n--- Recovery Index (reasoning_calls / val_calls) ---")
    print(f"{'Model':<22s} {'mean_RI':>8s} {'mean_score':>11s}")
    print("-" * 45)
    ri_rows = []
    for model in MODEL_ORDER:
        sub = has_val[has_val["model"] == model]
        if len(sub) == 0:
            continue
        ri = sub["recovery_index"].mean()
        sc = sub["score"].mean()
        print(f"{MODEL_SHORT_NAMES.get(model, model):<22s} {ri:8.2f} {sc:11.3f}")
        ri_rows.append({"model": MODEL_SHORT_NAMES.get(model, model),
                        "mean_recovery_index": ri, "mean_tool_score": sc})
    if ri_rows:
        pd.DataFrame(ri_rows).to_csv(
            output_dir / "deep_anchoring_recovery.csv", index=False
        )
        print(f"Saved: {output_dir / 'deep_anchoring_recovery.csv'}")
    else:
        print("WARNING: no recovery index data — CSV not written.")

    # Figure: invalid_ratio vs score, colored by task type
    fig, ax = plt.subplots(figsize=(7, 5))
    for task in TASK_TYPE_ORDER:
        sub = valid[valid["task_type"] == task]
        if len(sub) < 3:
            continue
        ax.scatter(sub["val_invalid_ratio"], sub["score"],
                   label=task, alpha=0.4, s=15)
    ax.set_xlabel("Invalid Descriptor Ratio")
    ax.set_ylabel("Score (tool condition)")
    ax.set_title("Anchoring: Invalid Descriptors vs. Score")
    ax.legend(title="Task", fontsize=7, title_fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "deep_anchoring_scatter.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"\nFigure: {output_dir / 'deep_anchoring_scatter.pdf'}")


# ---------------------------------------------------------------------------
# 2. Prompt-level anchoring (zero-call models)
# ---------------------------------------------------------------------------

def prompt_anchoring_analysis(df, output_dir):
    """Analyze models that make 0 reasoning tool calls but still show
    negative delta.

    Some models (e.g. GPT-5.4) rarely or never call reasoning tools, yet
    score lower in the tool condition. This suggests the system prompt's
    epistemic framing alone -- "only treat confirmed results as positive
    evidence" -- is enough to degrade performance by causing models to
    second-guess their own parametric knowledge.

    Zero-call is defined as ``reasoning_calls == 0`` (covers both
    validate_descriptors and the graph-traversal tools). The score_drift
    rate captures any score change > 0.01 between conditions; this equals
    the answer flip rate for binary tasks and measures score movement for
    F1 / judge-scored tasks. Per-task breakdown is printed for the two
    hardcoded headline models (gpt-5.4, nemotron).
    """
    print("\n" + "=" * 60)
    print("2. PROMPT-LEVEL ANCHORING (zero-call behavior)")
    print("=" * 60)

    paired = get_paired_scores(df)

    # Merge tool-condition metrics
    tool_metrics = df[df["condition"] == "tool"][
        ["model", "question_id", "reasoning_calls", "answered_early"]
    ]
    paired = paired.merge(tool_metrics, on=["model", "question_id"], how="left")

    # Split: zero-call vs nonzero-call
    zero_call = paired[paired["reasoning_calls"] == 0].copy()
    nonzero_call = paired[paired["reasoning_calls"] > 0].copy()

    print(f"\nZero-call pairs: {len(zero_call)}, Nonzero-call pairs: {len(nonzero_call)}")

    # Per model: zero-call Δ vs nonzero-call Δ
    print(f"\n{'Model':<22s} {'n_zero':>7s} {'Δ_zero':>8s} {'n_nonzero':>10s} {'Δ_nonzero':>10s} {'drift%':>10s}")
    print("-" * 72)
    rows = []
    for model in MODEL_ORDER:
        zc = zero_call[zero_call["model"] == model]
        nzc = nonzero_call[nonzero_call["model"] == model]

        dz = zc["delta"].mean() if len(zc) > 0 else np.nan
        dnz = nzc["delta"].mean() if len(nzc) > 0 else np.nan

        # Score-drift rate: fraction of paired items whose score changed by
        # more than 0.01 between conditions. For binary tasks this equals
        # answer flip rate; for F1 / judge scores it measures any score
        # movement (answer may be "almost identical" with different wording).
        if len(zc) > 0:
            score_drift = (np.abs(zc["score_no_tool"] - zc["score_tool"]) > 0.01).mean()
        else:
            score_drift = np.nan

        print(f"{MODEL_SHORT_NAMES.get(model, model):<22s} {len(zc):7d} {dz:+8.4f} "
              f"{len(nzc):10d} {dnz:+10.4f} {score_drift:10.1%}" if not np.isnan(score_drift) else
              f"{MODEL_SHORT_NAMES.get(model, model):<22s} {len(zc):7d} {'N/A':>8s} "
              f"{len(nzc):10d} {'N/A':>10s} {'N/A':>10s}")

        rows.append({"model": MODEL_SHORT_NAMES.get(model, model),
                      "n_zero_call": len(zc), "delta_zero_call": dz,
                      "n_nonzero_call": len(nzc), "delta_nonzero_call": dnz,
                      "score_drift_rate": score_drift})

    pd.DataFrame(rows).to_csv(output_dir / "deep_prompt_anchoring.csv", index=False)

    # Per task type for key models (gpt-5.4, nemotron)
    for model_name in ["gpt-5.4", "nemotron-3-super-120b-a12b"]:
        zc = zero_call[zero_call["model"] == model_name]
        if len(zc) == 0:
            continue
        print(f"\n--- {MODEL_SHORT_NAMES.get(model_name, model_name)} zero-call by task ---")
        for task in TASK_TYPE_ORDER:
            sub = zc[zc["task_type"] == task]
            if len(sub) == 0:
                continue
            drift = (np.abs(sub["score_no_tool"] - sub["score_tool"]) > 0.01).mean()
            print(f"  {task}: n={len(sub):3d}  Δ={sub['delta'].mean():+.4f}  drift={drift:.1%}")


# ---------------------------------------------------------------------------
# 3. Tool-skip analysis
# ---------------------------------------------------------------------------

def tool_skip_analysis(df, output_dir):
    """Compare tool-skippers (reasoning_calls=0) vs tool-users.

    Disentangles two sources of harm: (1) prompt-level anchoring that
    affects all models in the tool condition regardless of tool use, and
    (2) tool-interaction harm from acting on misleading tool outputs.
    If tool-skippers match the no_tool baseline, harm is purely from
    tool engagement; if they also degrade, prompt framing is a factor.

    Caveat: the skip/use split is observational, not randomised. Whether
    a model calls tools is correlated with the model itself, task type,
    and perceived question difficulty. Δ differences between groups
    therefore conflate selection effects with the prompt / tool effect
    and should be interpreted as descriptive, not causal.
    """
    print("\n" + "=" * 60)
    print("3. TOOL-SKIP ANALYSIS")
    print("=" * 60)

    tool_df = df[df["condition"] == "tool"].copy()

    # Merge no_tool scores
    no_tool_scores = df[df["condition"] == "no_tool"][["model", "question_id", "score"]].rename(
        columns={"score": "score_no_tool"}
    )
    tool_df = tool_df.merge(no_tool_scores, on=["model", "question_id"])

    tool_df["used_tools"] = tool_df["reasoning_calls"] > 0
    tool_df["delta"] = tool_df["score"] - tool_df["score_no_tool"]

    # Overall
    skip = tool_df[~tool_df["used_tools"]]
    use = tool_df[tool_df["used_tools"]]
    print(f"\nTool-skippers: {len(skip)} ({len(skip)/len(tool_df):.1%})")
    print(f"Tool-users:    {len(use)} ({len(use)/len(tool_df):.1%})")
    print(f"\nSkipper mean Δ:  {skip['delta'].mean():+.4f}")
    print(f"User mean Δ:     {use['delta'].mean():+.4f}")

    # Per model
    print(f"\n{'Model':<22s} {'%skip':>6s} {'Δ_skip':>8s} {'Δ_use':>8s} {'gap':>8s}")
    print("-" * 56)
    rows = []
    for model in MODEL_ORDER:
        sk = tool_df[(tool_df["model"] == model) & (~tool_df["used_tools"])]
        us = tool_df[(tool_df["model"] == model) & (tool_df["used_tools"])]
        pct = len(sk) / (len(sk) + len(us)) if (len(sk) + len(us)) > 0 else 0
        d_sk = sk["delta"].mean() if len(sk) > 0 else np.nan
        d_us = us["delta"].mean() if len(us) > 0 else np.nan
        gap = d_sk - d_us if pd.notna(d_sk) and pd.notna(d_us) else np.nan
        print(f"{MODEL_SHORT_NAMES.get(model, model):<22s} {pct:6.1%} "
              f"{d_sk:+8.4f} {d_us:+8.4f} {gap:+8.4f}" if pd.notna(gap) else
              f"{MODEL_SHORT_NAMES.get(model, model):<22s} {pct:6.1%} "
              f"{'N/A':>8s} {'N/A':>8s} {'N/A':>8s}")
        rows.append({"model": MODEL_SHORT_NAMES.get(model, model),
                      "pct_skip": pct, "delta_skip": d_sk, "delta_use": d_us})

    pd.DataFrame(rows).to_csv(output_dir / "deep_tool_skip.csv", index=False)


# ---------------------------------------------------------------------------
# 4. Token cost analysis
# ---------------------------------------------------------------------------

def _load_pricing():
    """Load per-model pricing (USD per 1M tokens) from configs/models.yaml.

    Reads only the ``closed_source`` and ``open_source`` groups. Models
    under any other YAML section will be missing and priced at $0.00 by
    the caller; callers should check for missing keys and warn.
    Returns: dict {short_name: (input_price, output_price)}.
    """
    import yaml
    yaml_path = Path(__file__).resolve().parents[2] / "configs" / "models.yaml"
    with open(yaml_path) as f:
        cfg = yaml.safe_load(f)

    pricing = {}
    for group in ["closed_source", "open_source"]:
        for model in cfg.get(group, []):
            # Extract short name from model id (e.g., "anthropic/claude-sonnet-4.6" -> "claude-sonnet-4.6")
            model_id = model["id"]
            short = model_id.split("/", 1)[1] if "/" in model_id else model_id
            p = model.get("pricing", {})
            pricing[short] = (p.get("input", 0), p.get("output", 0))
    return pricing


def token_cost_analysis(df, output_dir):
    """Token consumption and cost by condition.

    Motivation: the paper claims tool access is a "cost of degradation" —
    more tokens (and dollars) for lower scores. This function quantifies
    both sides of that trade-off.

    Token counts: API-reported (prompt_tokens + completion_tokens),
    summed across all turns per evaluation.
    Prices: OpenRouter published rates (configs/models.yaml).
    Cost = tokens x price / 1_000_000. No real billing data available.
    Missing pricing -> $0.00 (warned explicitly above the table).
    """
    print("\n" + "=" * 60)
    print("4. TOKEN COST ANALYSIS")
    print("=" * 60)
    print("  (Tokens: API-reported. Prices: OpenRouter published rates. Cost = tokens × price.)")

    pricing = _load_pricing()

    # Warn on any model with missing pricing before printing the cost table
    missing = [m for m in MODEL_ORDER if m not in pricing]
    if missing:
        print(f"  WARNING: no pricing for {len(missing)} model(s); cost shown as $0.00:")
        for m in missing:
            print(f"    - {m}")

    print(f"\n{'Model':<22s} {'Cond':<8s} {'In_tok':>8s} {'Out_tok':>9s} {'Total':>9s} "
          f"{'Latency':>8s} {'Cost':>8s}")
    print("-" * 80)

    rows = []
    for model in MODEL_ORDER:
        for cond in ["no_tool", "tool"]:
            sub = df[(df["model"] == model) & (df["condition"] == cond)]
            in_tok = sub["input_tokens"].mean()
            out_tok = sub["output_tokens"].mean()
            total = sub["total_tokens"].mean()
            lat = sub["latency_ms"].mean()

            # Cost estimate per eval
            price_in, price_out = pricing.get(model, (0, 0))
            cost = (in_tok * price_in + out_tok * price_out) / 1_000_000

            print(f"{MODEL_SHORT_NAMES.get(model, model):<22s} {cond:<8s} "
                  f"{in_tok:8.0f} {out_tok:9.0f} {total:9.0f} "
                  f"{lat:8.0f} ${cost:7.4f}")

            rows.append({
                "model": MODEL_SHORT_NAMES.get(model, model),
                "condition": cond,
                "mean_input_tokens": in_tok,
                "mean_output_tokens": out_tok,
                "mean_total_tokens": total,
                "mean_latency_ms": lat,
                "cost_per_eval": cost,
            })

    cost_df = pd.DataFrame(rows)
    cost_df.to_csv(output_dir / "deep_token_cost.csv", index=False)

    # Summary: tool overhead ratio
    print(f"\n--- Tool Overhead (tool / no_tool ratio) ---")
    for model in MODEL_ORDER:
        nt = cost_df[(cost_df["model"] == MODEL_SHORT_NAMES.get(model, model)) &
                     (cost_df["condition"] == "no_tool")]
        t = cost_df[(cost_df["model"] == MODEL_SHORT_NAMES.get(model, model)) &
                    (cost_df["condition"] == "tool")]
        if len(nt) > 0 and len(t) > 0:
            ratio = t.iloc[0]["mean_total_tokens"] / nt.iloc[0]["mean_total_tokens"]
            cost_ratio = t.iloc[0]["cost_per_eval"] / nt.iloc[0]["cost_per_eval"] if nt.iloc[0]["cost_per_eval"] > 0 else np.inf
            print(f"  {MODEL_SHORT_NAMES.get(model, model):<22s} "
                  f"tokens: {ratio:.1f}×  cost: {cost_ratio:.1f}×")


# ---------------------------------------------------------------------------
# 5. Parse error audit
# ---------------------------------------------------------------------------

def parse_error_audit(df, output_dir):
    """Document non-success cases and verify they don't flip Δ sign.

    Two classes of non-success:
      - parse_error: model replied but the answer extraction failed (scores 0).
      - tool_error: an API or tool-call failure (should be excluded or
        counted depending on whether it reflects model behaviour).

    Robustness criterion: recompute each model's macro Δ after dropping
    all non-success rows, then check whether the sign of Δ changes. Sign
    preservation means the main result ("tools hurt") does not depend on
    how we treat these edge cases. Exclusion is all-or-nothing per row,
    not per-task-type.
    """
    print("\n" + "=" * 60)
    print("5. PARSE ERROR AUDIT")
    print("=" * 60)

    non_success = df[df["status"] != "success"].copy()
    print(f"\nNon-success cases: {len(non_success)}/{len(df)} ({len(non_success)/len(df):.2%})")

    # Breakdown
    print(f"\n{'Model':<22s} {'Condition':<9s} {'Status':<15s} {'Count':>5s} {'Task Types'}")
    print("-" * 75)
    for (model, cond, status), group in non_success.groupby(["model", "condition", "status"]):
        tasks = ", ".join(sorted(group["task_type"].unique()))
        print(f"{MODEL_SHORT_NAMES.get(model, model):<22s} {cond:<9s} {status:<15s} "
              f"{len(group):5d} {tasks}")

    # Impact analysis: would removing these change Δ direction?
    print(f"\n--- Impact Check: Does excluding non-success change Δ sign? ---")
    success_only = df[df["status"] == "success"]

    from scripts.analysis.load_data import compute_macro_scores
    full_scores = compute_macro_scores(df)
    clean_scores = compute_macro_scores(success_only)

    for model in MODEL_ORDER:
        full_nt = full_scores[(full_scores["model"] == model) & (full_scores["condition"] == "no_tool")]
        full_t = full_scores[(full_scores["model"] == model) & (full_scores["condition"] == "tool")]
        clean_nt = clean_scores[(clean_scores["model"] == model) & (clean_scores["condition"] == "no_tool")]
        clean_t = clean_scores[(clean_scores["model"] == model) & (clean_scores["condition"] == "tool")]

        if len(full_nt) == 0 or len(full_t) == 0:
            continue

        full_delta = full_t.iloc[0]["macro_score"] - full_nt.iloc[0]["macro_score"]
        clean_delta = clean_t.iloc[0]["macro_score"] - clean_nt.iloc[0]["macro_score"]

        sign_change = "CHANGED" if (full_delta * clean_delta < 0) else "same"
        print(f"  {MODEL_SHORT_NAMES.get(model, model):<22s} "
              f"full Δ={full_delta:+.4f}  clean Δ={clean_delta:+.4f}  [{sign_change}]")

    non_success.to_csv(output_dir / "deep_parse_errors.csv", index=False)


# ---------------------------------------------------------------------------
# 6. Vocabulary gap analysis
# ---------------------------------------------------------------------------

def vocabulary_gap_analysis(df, output_dir):
    """NONE-response inflation and A1 correct-answer vocabulary split.

    Tests the vocabulary gap mechanism: the 111-node tool graph covers only
    a fraction of real-world flavor vocabulary, so validate_descriptors
    returns "invalid" for virtually every descriptor in the question set.
    Models treat this false-negative as evidence of no answer and select
    NONE — even when a correct answer is reachable from parametric knowledge.

    Part A — NONE inflation:
        Compares NONE-selection rate across conditions and task types.
        Under no_tool, models rarely select NONE (~6%). Under tool, invalid
        signals inflate the rate to ~23%; 81% of tool-NONE answers are wrong.

    Part B — A1 vocabulary split:
        A1 answer options are root category names; 7 of 9 appear in the tool
        graph but 2 (floral, green/vegetable) do not. Questions whose correct
        root IS in the tool graph show positive Δ (tool confirms the right
        answer). Questions whose correct root is NOT in the tool graph show
        strongly negative Δ (invalid signal triggers anchoring). The ~0.30
        swing in Δ is the cleanest direct test of the vocabulary gap claim.

    See docs/memo_vocabulary_gap_anchoring_20260420.md for full discussion.
    """
    import pickle

    print("\n" + "=" * 60)
    print("6. VOCABULARY GAP ANALYSIS")
    print("=" * 60)

    # Load tool graph node names
    tool_graph_path = Path(__file__).resolve().parents[2] / "data" / "graphs" / "coffee_flavor_wheel.pkl"
    with open(tool_graph_path, "rb") as f:
        tool_graph = pickle.load(f)
    tool_nodes_lower = {str(n).lower() for n in tool_graph.nodes()}

    df = df.copy()

    # -------------------------------------------------------------------------
    # Part A: NONE inflation
    # -------------------------------------------------------------------------
    print("\n--- A. NONE-Response Rate by Condition ---")

    # parse_pattern contains "pattern_matched" from the answer parser.
    # The multi-select parser always suffixes NONE responses with " (NONE)"
    # (e.g. "I select (...) (NONE)"), so matching the literal "(NONE)" is
    # precise and avoids false positives from other pattern names.
    df["is_none"] = df["parse_pattern"].str.contains("(NONE)", regex=False, na=False)

    none_rows = []
    for cond in ["no_tool", "tool"]:
        sub = df[df["condition"] == cond]
        n_none = int(sub["is_none"].sum())
        rate = sub["is_none"].mean()
        n_wrong_none = int(sub[sub["is_none"] & (sub["score"] == 0)].shape[0])
        pct_wrong = n_wrong_none / n_none if n_none > 0 else np.nan
        print(f"  {cond:<10s}: NONE rate={rate:.1%}  "
              f"n_none={n_none}  pct_wrong={pct_wrong:.1%}")
        none_rows.append({"condition": cond, "none_rate": rate,
                          "n_none": n_none, "pct_none_wrong": pct_wrong})

    print(f"\n  {'Task':<6s} {'no_tool NONE%':>14s} {'tool NONE%':>11s} {'ΔNONE%':>9s}")
    print("  " + "-" * 44)
    task_none_rows = []
    for task in TASK_TYPE_ORDER:
        nt = df[(df["condition"] == "no_tool") & (df["task_type"] == task)]
        t = df[(df["condition"] == "tool") & (df["task_type"] == task)]
        nt_rate = nt["is_none"].mean() if len(nt) > 0 else np.nan
        t_rate = t["is_none"].mean() if len(t) > 0 else np.nan
        delta = (t_rate - nt_rate) if pd.notna(nt_rate) and pd.notna(t_rate) else np.nan
        flag = " <-- extreme" if pd.notna(delta) and delta > 0.15 else ""
        print(f"  {task:<6s} {nt_rate:14.1%} {t_rate:11.1%} {delta:+9.1%}{flag}")
        task_none_rows.append({"task_type": task, "none_rate_no_tool": nt_rate,
                                "none_rate_tool": t_rate, "none_rate_delta": delta})

    pd.DataFrame(none_rows).to_csv(output_dir / "deep_none_inflation.csv", index=False)
    pd.DataFrame(task_none_rows).to_csv(
        output_dir / "deep_none_inflation_by_task.csv", index=False
    )

    # -------------------------------------------------------------------------
    # Part B: A1 correct-answer vocabulary split
    # -------------------------------------------------------------------------
    print("\n--- B. A1 Correct-Answer Vocabulary Split ---")
    print("  Splits A1 questions by whether the correct root category")
    print("  appears in the 111-node tool graph vocabulary.")

    questions_path = (
        Path(__file__).resolve().parents[2]
        / "data" / "questions" / "all_questions_system.json"
    )
    with open(questions_path) as fq:
        questions_data = json.load(fq)

    # Build question_id -> set of correct option texts (lower-cased).
    # correct_answer is expected to be a letter key ("B") or list of keys
    # (["B", "C"]) that index into the options dict. If it contains option
    # texts instead of keys, options.get() will return "" and texts will be
    # empty — logged as a warning so silent misclassification is detectable.
    q_correct_texts = {}
    for q in questions_data:
        if q.get("task_type") != "A1":
            continue
        options = q.get("options", {})
        correct = q.get("correct_answer", [])
        if isinstance(correct, str):
            correct = [correct]
        texts = {options.get(ltr, "").lower().strip()
                 for ltr in correct if ltr in options}
        texts.discard("")  # remove empty strings from failed key lookups
        qid = q.get("id") or q.get("question_id")
        if qid:
            if correct and not texts:
                print(f"  WARNING: question {qid} has correct_answer {correct!r} "
                      f"but no matching option keys — check correct_answer format.")
            q_correct_texts[qid] = texts

    a1_df = df[df["task_type"] == "A1"].copy()
    a1_df["any_correct_in_vocab"] = a1_df["question_id"].apply(
        lambda qid: any(t in tool_nodes_lower
                        for t in q_correct_texts.get(qid, set()) if t)
    )

    # Identify and explicitly exclude unmapped questions before pairing so
    # they don't silently fall into the "correct_not_in_vocab" group.
    unmapped_qids = a1_df["question_id"].apply(
        lambda qid: qid not in q_correct_texts
    )
    if unmapped_qids.any():
        n_unmapped_rows = int(unmapped_qids.sum())
        n_unmapped_questions = a1_df.loc[unmapped_qids, "question_id"].nunique()
        print(f"  WARNING: {n_unmapped_questions} A1 question(s) had no mapping "
              f"({n_unmapped_rows} evaluation rows) — excluded from split.")
        a1_df = a1_df[~unmapped_qids]

    a1_paired = get_paired_scores(a1_df)
    # Drop rows where either condition score is missing (unpaired questions)
    n_before = len(a1_paired)
    a1_paired = a1_paired.dropna(subset=["score_no_tool", "score_tool"])
    if len(a1_paired) < n_before:
        print(f"  Dropped {n_before - len(a1_paired)} unpaired A1 question×model rows.")
    q_vocab = (
        a1_df[["question_id", "any_correct_in_vocab"]]
        .drop_duplicates("question_id")
    )
    a1_paired = a1_paired.merge(q_vocab, on="question_id")

    split_results = []
    for label, mask in [("correct_in_vocab", a1_paired["any_correct_in_vocab"]),
                        ("correct_not_in_vocab", ~a1_paired["any_correct_in_vocab"])]:
        sub = a1_paired[mask]
        if len(sub) == 0:
            continue
        nt_mean = sub["score_no_tool"].mean()
        t_mean = sub["score_tool"].mean()
        delta = sub["delta"].mean()
        print(f"\n  {label} (n={len(sub)}):")
        print(f"    no_tool acc = {nt_mean:.3f}   tool acc = {t_mean:.3f}   Δ = {delta:+.3f}")

        diff = sub["score_tool"].values - sub["score_no_tool"].values
        # Use a tolerance threshold rather than exact equality: F1 scores can
        # produce floating-point near-zero differences that are not true ties.
        nonzero = diff[np.abs(diff) > 1e-9]
        if len(nonzero) >= 5:
            # nan_policy="raise" added in scipy 1.7; the dropna above already
            # guarantees no NaNs, so omitting it is safe and more portable.
            stat, p = stats.wilcoxon(
                sub["score_no_tool"].values, sub["score_tool"].values,
                alternative="two-sided"
            )
            print(f"    Wilcoxon: W={stat:.0f}  p={p:.2e}")
        else:
            stat, p = np.nan, np.nan

        split_results.append({
            "group": label,
            "n_pairs": len(sub),
            "mean_no_tool": nt_mean,
            "mean_tool": t_mean,
            "mean_delta": delta,
            "wilcoxon_W": stat,
            "wilcoxon_p": p,
        })

    pd.DataFrame(split_results).to_csv(
        output_dir / "deep_vocab_gap_a1_split.csv", index=False
    )
    print(f"\n  Saved: {output_dir / 'deep_vocab_gap_a1_split.csv'}")
    print(f"  Saved: {output_dir / 'deep_none_inflation.csv'}")
    print(f"  Saved: {output_dir / 'deep_none_inflation_by_task.csv'}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Deep analysis")
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--output-dir", default="results/analysis")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_all_evaluations(args.results_dir)

    anchoring_analysis(df, output_dir)
    prompt_anchoring_analysis(df, output_dir)
    tool_skip_analysis(df, output_dir)
    token_cost_analysis(df, output_dir)
    parse_error_audit(df, output_dir)
    vocabulary_gap_analysis(df, output_dir)


if __name__ == "__main__":
    main()
