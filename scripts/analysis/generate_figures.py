"""
Generate Figures 1-3 for the paper.

These figures visualise three complementary perspectives on tool-augmented
performance, progressing from aggregate to fine-grained.

Terminology: the *tool graph* is the 111-node SCAA wheel exposed to models
in the tool condition; the *system graph* is the larger ground-truth graph
used to author questions (a superset of the tool graph). A3/E3 are
"productive" task types because their questions resolve at category nodes
where the tool graph has good coverage; A4/A5 are "misleading" because
they require leaf-level validation where the tool graph has gaps.

Figure 1 — Tool Δ by Task Type
    Bar chart showing the average score change (tool − no_tool) per task
    type, with ±1 SE error bars and individual model dots overlaid.
    Answers: *which task types benefit from tools and which are harmed?*
    Green bars (positive Δ) indicate categories where the tool graph has
    sufficient coverage for productive lookups; red bars highlight
    categories where the coverage gap causes anchoring harm.

Figure 2 — Reasoning Calls vs. Score Δ
    Scatter plot of (mean reasoning_calls, Δ) per model × task_type cell.
    ``reasoning_calls`` counts *all* reasoning tool invocations in the
    tool condition (validate_descriptors + get_parent + get_children +
    get_siblings), so it acts as a proxy for total engagement rather than
    a pure count of validate calls. Answers: *does heavier tool engagement
    correlate with more or less harm?*  Reveals that tool harm is roughly
    proportional to engagement on misleading tasks, while productive
    tasks (A3, E3) form a separate cluster with positive Δ despite high
    call counts.

Figure 3 — Per-Question Paired Heatmap
    275 × 11 heatmap of per-question Δ, sorted by task type then mean Δ.
    Answers: *is tool harm question-specific or model-specific?*  Vertical
    colour bands within a task type suggest certain questions consistently
    help or hurt across all models, pointing to structural properties of
    those questions rather than model-level idiosyncrasies.

Usage:
    python scripts/analysis/generate_figures.py
    python scripts/analysis/generate_figures.py --output-dir results/analysis
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scripts.analysis.load_data import (
    load_all_evaluations, compute_deltas, get_paired_scores,
    compute_per_task_scores, MODEL_ORDER, MODEL_SHORT_NAMES,
    MODEL_TO_GROUP, TASK_TYPE_ORDER,
)

# Style
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8,
    "figure.dpi": 150,
})

TASK_COLORS = {
    "A1": "#1f77b4", "A2": "#2ca02c", "A3": "#ff7f0e",
    "A4": "#d62728", "A5": "#9467bd",
    "E1": "#8c564b", "E2": "#e377c2", "E3": "#17becf",
    "F": "#7f7f7f",
}

GROUP_MARKERS = {
    "Closed-source": "o",
    "Thinking-token": "s",
    "Open-source": "^",
}


def figure1_tool_delta_by_task(df, output_dir):
    """Figure 1: Tool Δ by task type with model-level dots.

    Bars show mean Δ across models per task type with ±1 SE error bars.
    Colour encoding: green = positive Δ (tool helped), red = negative Δ
    (tool hurt). Individual model dots are overlaid with horizontal
    jitter; marker shape encodes model group (circle = closed-source,
    square = thinking-token, triangle = open-source), so readers can see
    per-model variance and group clustering at a glance.

    Output: ``figure1_tool_delta_by_task.pdf``.
    """
    deltas = compute_deltas(df)

    # Average Δ per task type
    task_avg = deltas.groupby("task_type")["delta"].agg(["mean", "std", "count"]).reset_index()
    task_avg["se"] = task_avg["std"] / np.sqrt(task_avg["count"])
    task_avg["task_order"] = task_avg["task_type"].map(
        {t: i for i, t in enumerate(TASK_TYPE_ORDER)}
    )
    task_avg = task_avg.sort_values("task_order")

    fig, ax = plt.subplots(figsize=(7, 4))

    # Bars
    x = np.arange(len(task_avg))
    colors = [("#2ca02c" if m > 0 else "#d62728") for m in task_avg["mean"]]
    bars = ax.bar(x, task_avg["mean"], color=colors, alpha=0.7, edgecolor="gray",
                  linewidth=0.5, zorder=2)

    # Error bars (±1 SE)
    ax.errorbar(x, task_avg["mean"], yerr=task_avg["se"],
                fmt="none", color="black", capsize=3, capthick=1, zorder=3)

    # Individual model dots
    for _, row in deltas.iterrows():
        task_idx = TASK_TYPE_ORDER.index(row["task_type"]) if row["task_type"] in TASK_TYPE_ORDER else -1
        if task_idx < 0:
            continue
        group = MODEL_TO_GROUP.get(row["model"], "Unknown")
        marker = GROUP_MARKERS.get(group, "o")
        jitter = np.random.uniform(-0.2, 0.2)
        ax.scatter(task_idx + jitter, row["delta"], marker=marker,
                   s=15, color="black", alpha=0.4, zorder=4, linewidths=0.3)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="-", zorder=1)
    ax.set_xticks(x)
    ax.set_xticklabels(TASK_TYPE_ORDER)
    ax.set_xlabel("Task Type")
    ax.set_ylabel("Tool Δ (tool − no_tool)")
    ax.set_title("Tool Effect by Task Type")

    # Legend for model groups
    for group, marker in GROUP_MARKERS.items():
        ax.scatter([], [], marker=marker, s=20, color="black", alpha=0.5, label=group)
    ax.legend(loc="lower left", framealpha=0.9)

    ax.set_ylim(ax.get_ylim()[0] - 0.05, ax.get_ylim()[1] + 0.05)
    fig.tight_layout()

    path = output_dir / "figure1_tool_delta_by_task.pdf"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"Figure 1: {path}")


def figure2_tool_calls_vs_delta(df, output_dir):
    """Figure 2: Reasoning calls vs. score Δ (scatter per model x task_type).

    Each point represents one (model, task_type) cell. The x-axis
    (``reasoning_calls``) counts all reasoning-tool invocations in the
    tool condition — validate_descriptors plus the graph-traversal tools
    — so it acts as a proxy for total engagement, not just validate
    calls. Colour encodes task type; shape is not used (all markers are
    circles). 99 points total (11 models x 9 task types).

    Output: ``figure2_tool_calls_vs_delta.pdf``.
    """
    # Average reasoning_calls per model × task_type (tool condition only)
    tool_df = df[df["condition"] == "tool"]
    avg_calls = (
        tool_df.groupby(["model", "task_type"])["reasoning_calls"]
        .mean()
        .reset_index()
        .rename(columns={"reasoning_calls": "avg_calls"})
    )

    # Deltas per model × task_type
    deltas = compute_deltas(df)
    merged = deltas.merge(avg_calls, on=["model", "task_type"])
    merged["model_group"] = merged["model"].map(MODEL_TO_GROUP)

    fig, ax = plt.subplots(figsize=(7, 5))

    for task in TASK_TYPE_ORDER:
        subset = merged[merged["task_type"] == task]
        ax.scatter(subset["avg_calls"], subset["delta"],
                   c=TASK_COLORS.get(task, "gray"), label=task,
                   s=30, alpha=0.7, edgecolors="gray", linewidths=0.3)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="-", zorder=1)
    ax.set_xlabel("Average Reasoning Calls (tool condition)")
    ax.set_ylabel("Tool Δ (tool − no_tool)")
    ax.set_title("Tool Engagement vs. Score Change")

    ax.legend(title="Task Type", bbox_to_anchor=(1.02, 1), loc="upper left",
              fontsize=8, title_fontsize=9)

    fig.tight_layout()
    path = output_dir / "figure2_tool_calls_vs_delta.pdf"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"Figure 2: {path}")


def figure3_paired_heatmap(df, output_dir):
    """Figure 3: Per-question paired heatmap (delta across models).

    Rows are the 275 questions sorted by (task_type, mean Δ within task
    type); columns are the 11 models in MODEL_ORDER. Cell colour is the
    paired Δ = score_tool - score_no_tool for that (question, model),
    using a diverging colormap centred at 0 (blue = tool helped, red =
    tool hurt). Black horizontal lines mark task-type boundaries, and
    task labels appear on the right axis. This layout makes vertical
    bands of consistent colour identify question-specific effects (same
    question hurts/helps across models), while horizontal streaks
    identify model-specific effects.

    Output: ``figure3_paired_heatmap.pdf``.
    """
    paired = get_paired_scores(df)

    # Pivot: questions × models
    pivot = paired.pivot_table(
        index="question_id", columns="model", values="delta"
    )

    # Add task_type for sorting
    q_task = paired[["question_id", "task_type"]].drop_duplicates().set_index("question_id")
    pivot = pivot.join(q_task)

    # Sort by task_type, then by mean delta within type
    pivot["mean_delta"] = pivot[MODEL_ORDER].mean(axis=1)
    task_order_map = {t: i for i, t in enumerate(TASK_TYPE_ORDER)}
    pivot["_task_order"] = pivot["task_type"].map(task_order_map)
    pivot = pivot.sort_values(["_task_order", "mean_delta"])

    # Keep task labels for y-axis annotation
    task_labels = pivot["task_type"].values
    heatmap_data = pivot[[m for m in MODEL_ORDER if m in pivot.columns]]
    heatmap_data.columns = [MODEL_SHORT_NAMES.get(m, m) for m in heatmap_data.columns]

    fig, ax = plt.subplots(figsize=(10, 14))

    sns.heatmap(
        heatmap_data, ax=ax,
        cmap="RdBu", center=0, vmin=-1, vmax=1,
        xticklabels=True, yticklabels=False,
        cbar_kws={"label": "Tool Δ", "shrink": 0.6},
        linewidths=0,
    )

    # Add task type boundaries
    prev_task = None
    for i, task in enumerate(task_labels):
        if prev_task is not None and task != prev_task:
            ax.axhline(i, color="black", linewidth=1)
        prev_task = task

    # Add task type labels on right side
    task_positions = {}
    for i, task in enumerate(task_labels):
        if task not in task_positions:
            task_positions[task] = []
        task_positions[task].append(i)

    for task, positions in task_positions.items():
        mid = np.mean(positions)
        ax.text(len(heatmap_data.columns) + 0.3, mid, task,
                ha="left", va="center", fontsize=8, fontweight="bold")

    ax.set_xlabel("Model")
    ax.set_ylabel("Questions (sorted by task type, then mean Δ)")
    ax.set_title("Per-Question Tool Effect Across Models")

    fig.tight_layout()
    path = output_dir / "figure3_paired_heatmap.pdf"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"Figure 3: {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate paper figures")
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--output-dir", default="results/analysis")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    np.random.seed(42)
    df = load_all_evaluations(args.results_dir)

    figure1_tool_delta_by_task(df, output_dir)
    figure2_tool_calls_vs_delta(df, output_dir)
    figure3_paired_heatmap(df, output_dir)


if __name__ == "__main__":
    main()
