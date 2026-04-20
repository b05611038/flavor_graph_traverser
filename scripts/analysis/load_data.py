"""
Shared data loader for the analysis module.

Reads all 6,050 cache files into a single DataFrame with extracted metrics,
tool call details, and judge scores.

Experiment design
-----------------
We evaluate whether giving LLMs access to a structured knowledge tool (a
coffee-flavour-wheel graph) helps or hurts their performance on flavour-
knowledge questions.  Each of the 275 questions is answered by 11 models
under two conditions:

- **no_tool**: the model answers with its parametric knowledge only.
- **tool**: the model receives a system prompt and tool definitions for
  ``validate_descriptors``, ``get_parent``, ``get_children``, and
  ``get_siblings`` operating on a 111-node SCAA flavour wheel.  The model
  is free to call these tools (or not) before answering.

The 275 questions span 9 task types (A1-A5, E1-E3, F) with three scoring
methods:

- **Binary (A2/A3/E1/E2/E3):** score is 0 or 1 per question.
- **Multi-select F1 (A1/A4/A5):** score is the F1 of the model's selected
  options against the ground-truth set, in [0, 1].
- **Judge mean (F):** each of three LLM judges scores the response on a
  0-5 rubric; the pipeline averages the three and normalises to [0, 1]
  before writing ``score`` to the cache file. This loader reads the
  already-normalised score directly; raw 0-5 judge scores are preserved
  in the ``judge_score_*`` columns for inter-judge agreement analysis.

All downstream scores are therefore in [0, 1] and can be compared directly.

This module provides the canonical data loading and aggregation functions
used by every downstream analysis script.

Glossary (referenced across the analysis module):

- **tool graph:** the 111-node SCAA coffee flavour wheel exposed to models
  in the tool condition.
- **system graph:** the larger ground-truth graph used to author questions;
  a superset of the tool graph.
- **macro score:** mean of per-task-type averages (equal weight per task
  type regardless of question count).
- **micro score:** mean over all individual evaluations (weights task
  types by question count).
- **Δ (delta):** tool score minus no_tool score. Positive means tool
  helped; negative means tool hurt.

Usage:
    from scripts.analysis.load_data import load_all_evaluations
    df = load_all_evaluations()
    df = load_all_evaluations("results/merge_all")  # explicit path
"""

import json
import glob
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_RESULTS_DIR = _PROJECT_ROOT / "results" / "merge_all"
_MODELS_YAML = _PROJECT_ROOT / "configs" / "models.yaml"
_RESOLVED_MODELS = _PROJECT_ROOT / "data" / "resolved_models.json"

# Task types ordered for display
TASK_TYPE_ORDER = ["A1", "A2", "A3", "A4", "A5", "E1", "E2", "E3", "F"]

# Scoring method per task type
MULTI_SELECT_TYPES = {"A1", "A4", "A5"}  # F1 scoring
BINARY_TYPES = {"A2", "A3", "E1", "E2", "E3"}  # 0/1 scoring
JUDGE_TYPES = {"F"}  # mean(judge_scores)/5

# Judge model IDs
JUDGE_MODELS = [
    "anthropic/claude-opus-4.6",
    "google/gemini-3.1-pro-preview",
    "openai/gpt-5.4-pro",
]

# Model display names (short)
MODEL_SHORT_NAMES = {
    "claude-sonnet-4.6": "Sonnet 4.6",
    "gpt-5.4": "GPT-5.4",
    "gemini-3-flash-preview": "Gemini 3 Flash",
    "grok-4.1-fast": "Grok 4.1 Fast",
    "gpt-oss-120b": "GPT-OSS 120B",
    "qwen3.5-397b-a17b": "Qwen 3.5 397B",
    "kimi-k2.5": "Kimi K2.5",
    "llama-4-maverick": "Llama 4 Maverick",
    "deepseek-v3.2": "DeepSeek V3.2",
    "mistral-medium-3.1": "Mistral Medium 3.1",
    "nemotron-3-super-120b-a12b": "Nemotron 3 Super",
}

# Model groupings (verified from cache data: thinking_content presence)
MODEL_GROUPS = {
    "Thinking-token": [
        "gpt-oss-120b",
        "qwen3.5-397b-a17b",
        "kimi-k2.5",
        "nemotron-3-super-120b-a12b",
        "grok-4.1-fast",
    ],
    "Closed-source": [
        "claude-sonnet-4.6",
        "gpt-5.4",
        "gemini-3-flash-preview",
    ],
    "Open-source": [
        "deepseek-v3.2",
        "mistral-medium-3.1",
        "llama-4-maverick",
    ],
}

# Flat lookup: model -> group
MODEL_TO_GROUP = {}
for group, models in MODEL_GROUPS.items():
    for m in models:
        MODEL_TO_GROUP[m] = group

# Canonical model order for tables (group order, then alphabetical within)
MODEL_ORDER = []
for group in ["Closed-source", "Thinking-token", "Open-source"]:
    MODEL_ORDER.extend(sorted(MODEL_GROUPS[group]))


# ---------------------------------------------------------------------------
# Tool call extraction from conversation_history
# ---------------------------------------------------------------------------

def _extract_tool_calls(conversation_history):
    """Extract validate_descriptors call details from conversation history.

    Returns a list of dicts, one per validate_descriptors call:
      {"descriptors": [...], "valid": [...], "invalid": [...]}
    """
    if not conversation_history:
        return []

    # Build lookup: call_id -> descriptors queried
    calls_by_id = {}
    for msg in conversation_history:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                func = tc.get("function", {})
                if func.get("name") == "validate_descriptors":
                    call_id = tc.get("id")
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                        calls_by_id[call_id] = args.get("descriptors", [])
                    except (json.JSONDecodeError, TypeError):
                        pass

    # Match tool responses
    results = []
    for msg in conversation_history:
        if msg.get("role") == "tool" and msg.get("name") == "validate_descriptors":
            call_id = msg.get("tool_call_id")
            try:
                content = json.loads(msg.get("content", "{}"))
            except (json.JSONDecodeError, TypeError):
                continue
            results.append({
                "descriptors": calls_by_id.get(call_id, []),
                "valid": content.get("valid", []),
                "invalid": content.get("invalid", []),
            })

    return results


def _aggregate_tool_calls(validate_calls):
    """Aggregate validate_descriptors calls into summary metrics."""
    if not validate_calls:
        return {
            "val_total_checked": 0,
            "val_total_valid": 0,
            "val_total_invalid": 0,
            "val_invalid_ratio": np.nan,
            "val_call_count": 0,
        }
    total_checked = sum(len(c["descriptors"]) for c in validate_calls)
    total_valid = sum(len(c["valid"]) for c in validate_calls)
    total_invalid = sum(len(c["invalid"]) for c in validate_calls)
    return {
        "val_total_checked": total_checked,
        "val_total_valid": total_valid,
        "val_total_invalid": total_invalid,
        "val_invalid_ratio": total_invalid / total_checked if total_checked > 0 else np.nan,
        "val_call_count": len(validate_calls),
    }


# ---------------------------------------------------------------------------
# Single cache file parser
# ---------------------------------------------------------------------------

def _parse_cache_file(filepath):
    """Parse one cache JSON file into a flat dict for DataFrame construction."""
    with open(filepath) as f:
        data = json.load(f)

    metrics = data.get("metrics", {})
    if isinstance(metrics, list):
        # Some old files have metrics as a list of keys only
        metrics = {}

    parse_result = data.get("parse_result", {})
    if isinstance(parse_result, list):
        parse_result = {}

    # Extract model short name from the directory path
    # Path pattern: .../merge_all/{model_short}/cache/{provider}/{model}/...
    parts = Path(filepath).parts
    model_short = None
    for i, p in enumerate(parts):
        if p == "merge_all" and i + 1 < len(parts):
            model_short = parts[i + 1]
            break

    row = {
        "question_id": data.get("question_id"),
        "model": model_short or data.get("model", ""),
        "model_id": data.get("model", ""),
        "condition": data.get("condition"),
        "task_type": data.get("task_type", ""),
        "score": data.get("score", 0.0),
        "is_correct": data.get("is_correct", False),
        "status": data.get("status", "unknown"),
        "model_answer": data.get("model_answer"),
        "correct_answer": data.get("correct_answer"),
        "resolved_model": data.get("resolved_model"),

        # Metrics
        "reasoning_calls": metrics.get("reasoning_calls", 0),
        "validation_calls": metrics.get("validation_calls", 0),
        "total_turns": metrics.get("total_turns", 0),
        "input_tokens": metrics.get("input_tokens", 0),
        "output_tokens": metrics.get("output_tokens", 0),
        "total_tokens": metrics.get("total_tokens", 0),
        "latency_ms": metrics.get("latency_ms", 0),
        "answered_early": metrics.get("answered_early", False),

        # Parse result
        "parse_pattern": parse_result.get("pattern_matched", ""),
        "parse_answer": parse_result.get("answer", ""),

        # Judge scores (F-category)
        "judge_score_opus": None,
        "judge_score_gemini": None,
        "judge_score_gpt": None,
    }

    # Extract individual judge scores
    judge_scores = data.get("judge_scores", {})
    if judge_scores:
        row["judge_score_opus"] = judge_scores.get("anthropic/claude-opus-4.6")
        row["judge_score_gemini"] = judge_scores.get("google/gemini-3.1-pro-preview")
        row["judge_score_gpt"] = judge_scores.get("openai/gpt-5.4-pro")

    # Extract validate_descriptors details (tool condition only)
    if data.get("condition") == "tool":
        validate_calls = _extract_tool_calls(data.get("conversation_history", []))
        row.update(_aggregate_tool_calls(validate_calls))
    else:
        row.update({
            "val_total_checked": 0,
            "val_total_valid": 0,
            "val_total_invalid": 0,
            "val_invalid_ratio": np.nan,
            "val_call_count": 0,
        })

    return row


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_all_evaluations(results_dir=None, verbose=True):
    """Load all cache files into a single DataFrame.

    Args:
        results_dir: Path to merge_all directory. Defaults to results/merge_all.
        verbose: Print progress.

    Returns:
        pd.DataFrame with one row per evaluation (6,050 expected). Raw
        cache fields are augmented with three derived columns:
          - model_short: human-readable model name (from MODEL_SHORT_NAMES).
          - model_group: one of {Closed-source, Thinking-token, Open-source}.
          - scoring_method: one of {binary, F1, judge}.

        Tool-condition rows also include aggregated validate_descriptors
        metrics (val_total_checked, val_total_valid, val_total_invalid,
        val_invalid_ratio, val_call_count). Other reasoning tools
        (get_parent, get_children, get_siblings) are counted in the raw
        ``reasoning_calls`` metric but their call details are not parsed.
    """
    results_dir = Path(results_dir) if results_dir else _DEFAULT_RESULTS_DIR

    cache_files = sorted(glob.glob(
        str(results_dir / "*/cache/**/*.json"), recursive=True
    ))

    if not cache_files:
        raise FileNotFoundError(f"No cache files found in {results_dir}")

    if verbose:
        print(f"Loading {len(cache_files)} cache files from {results_dir}...")

    rows = []
    errors = []
    for i, fp in enumerate(cache_files):
        try:
            rows.append(_parse_cache_file(fp))
        except Exception as e:
            errors.append((fp, str(e)))
        if verbose and (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(cache_files)}")

    if errors:
        print(f"WARNING: {len(errors)} files failed to parse:")
        for fp, err in errors[:5]:
            print(f"  {fp}: {err}")

    df = pd.DataFrame(rows)

    # Derived columns
    df["model_short"] = df["model"].map(lambda m: MODEL_SHORT_NAMES.get(m, m))
    df["model_group"] = df["model"].map(lambda m: MODEL_TO_GROUP.get(m, "Unknown"))
    df["scoring_method"] = df["task_type"].map(
        lambda t: "F1" if t in MULTI_SELECT_TYPES
        else "judge" if t in JUDGE_TYPES
        else "binary"
    )

    # Sort for consistent ordering
    model_order_map = {m: i for i, m in enumerate(MODEL_ORDER)}
    task_order_map = {t: i for i, t in enumerate(TASK_TYPE_ORDER)}
    df["_model_order"] = df["model"].map(model_order_map)
    df["_task_order"] = df["task_type"].map(task_order_map)
    df = df.sort_values(["_model_order", "condition", "_task_order", "question_id"])
    df = df.drop(columns=["_model_order", "_task_order"])
    df = df.reset_index(drop=True)

    if verbose:
        print(f"Loaded {len(df)} evaluations: "
              f"{df['model'].nunique()} models, "
              f"{df['condition'].nunique()} conditions, "
              f"{df['question_id'].nunique()} questions")

    return df


# ---------------------------------------------------------------------------
# Convenience functions for common aggregations
# ---------------------------------------------------------------------------

def compute_macro_scores(df):
    """Compute macro and micro scores per model x condition.

    - macro_score: mean of per-task-type averages (equal weight per task
      type regardless of question count).
    - micro_score: mean over all individual evaluations (weights task
      types by their question count — A1/A2 with 50 questions each count
      more than F with 15).

    Returns DataFrame with columns: model, condition, macro_score,
    micro_score, model_short, model_group.
    """
    # Per model × condition × task_type average
    per_task = (
        df.groupby(["model", "condition", "task_type"])["score"]
        .mean()
        .reset_index()
        .rename(columns={"score": "task_avg"})
    )

    # Macro = mean of task averages
    macro = (
        per_task.groupby(["model", "condition"])["task_avg"]
        .mean()
        .reset_index()
        .rename(columns={"task_avg": "macro_score"})
    )

    # Micro = mean of all scores
    micro = (
        df.groupby(["model", "condition"])["score"]
        .mean()
        .reset_index()
        .rename(columns={"score": "micro_score"})
    )

    result = macro.merge(micro, on=["model", "condition"])

    # Add derived columns
    result["model_short"] = result["model"].map(lambda m: MODEL_SHORT_NAMES.get(m, m))
    result["model_group"] = result["model"].map(lambda m: MODEL_TO_GROUP.get(m, "Unknown"))

    return result


def compute_per_task_scores(df):
    """Compute per-task-type scores for each model × condition.

    Returns DataFrame pivoted: rows = model, columns = task_type × condition.
    """
    return (
        df.groupby(["model", "condition", "task_type"])["score"]
        .mean()
        .reset_index()
    )


def compute_deltas(df):
    """Compute tool delta (tool - no_tool) per model x task_type.

    Positive delta means the tool helped on that task type for that model;
    negative means the tool hurt. Scores are averaged within each
    (model, task_type, condition) cell before the subtraction.

    Returns DataFrame with columns: model, task_type, score_no_tool,
    score_tool, delta.
    """
    per_task = compute_per_task_scores(df)
    pivot = per_task.pivot_table(
        index=["model", "task_type"],
        columns="condition",
        values="score",
    ).reset_index()

    pivot.columns.name = None
    pivot = pivot.rename(columns={"no_tool": "score_no_tool", "tool": "score_tool"})
    pivot["delta"] = pivot["score_tool"] - pivot["score_no_tool"]
    return pivot


def get_paired_scores(df):
    """Get paired (no_tool, tool) scores per question x model.

    Unlike compute_deltas (which averages within a task type), this
    preserves per-question pairings — one row per (model, question_id).
    Used by Wilcoxon, McNemar, and per-question heatmaps where each
    question is its own paired control. Positive delta means tool helped.

    Returns DataFrame with columns: model, question_id, task_type,
    score_no_tool, score_tool, delta.
    """
    pivot = df.pivot_table(
        index=["model", "question_id", "task_type"],
        columns="condition",
        values="score",
    ).reset_index()

    pivot.columns.name = None
    pivot = pivot.rename(columns={"no_tool": "score_no_tool", "tool": "score_tool"})
    pivot["delta"] = pivot["score_tool"] - pivot["score_no_tool"]
    return pivot


# ---------------------------------------------------------------------------
# CLI: save to parquet
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Load all evaluations into DataFrame")
    parser.add_argument("--results-dir", default=None,
                        help="Path to merge_all directory")
    parser.add_argument("--output", default="results/analysis/all_evaluations.parquet",
                        help="Output parquet file path")
    args = parser.parse_args()

    df = load_all_evaluations(args.results_dir)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Convert mixed-type columns to string for parquet compatibility
    for col in ["model_answer", "correct_answer", "parse_answer"]:
        df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)
    df.to_parquet(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")

    # Quick summary
    print("\n--- Summary ---")
    scores = compute_macro_scores(df)
    for _, row in scores.sort_values(["model", "condition"]).iterrows():
        print(f"  {row['model_short']:<22s} {row['condition']:<8s}  "
              f"macro={row['macro_score']:.4f}  micro={row['micro_score']:.4f}")
