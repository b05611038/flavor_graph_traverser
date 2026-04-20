"""
Generate Tables 1 and 2 for the paper.

Research question
-----------------
Does access to a structured flavour-knowledge tool improve LLM accuracy on
flavour-reasoning tasks?  These tables present the top-level answer.

Table 1 — Model Leaderboard
    Compares each model's macro and micro scores under both conditions.
    *Macro score* (mean of per-task-type averages) gives equal weight to
    every task type regardless of question count; *micro score* (mean of all
    individual scores) reflects overall accuracy.  Models are grouped by
    architecture type (closed-source, thinking-token, open-source) so
    readers can see whether the tool effect varies across model families.

Table 2 — Per-Category Breakdown
    Shows no_tool / tool scores for every (model × task_type) cell.
    This reveals *where* tools help vs. hurt: task types whose questions can
    be resolved at the category level (A3, E3) tend to show positive Δ,
    while tasks requiring leaf-level validation (A4, A5) show large
    negative Δ because the 111-node *tool graph* (exposed to models) lacks
    many valid descriptors present in the full *system graph* used to
    author the questions.

Usage:
    python scripts/analysis/generate_tables.py
    python scripts/analysis/generate_tables.py --output-dir results/analysis
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import numpy as np
from scripts.analysis.load_data import (
    load_all_evaluations, compute_macro_scores, compute_per_task_scores,
    MODEL_ORDER, MODEL_SHORT_NAMES, MODEL_TO_GROUP, MODEL_GROUPS,
    TASK_TYPE_ORDER,
)


def generate_table1(df, output_dir):
    """Table 1: Model Leaderboard.

    One row per model, grouped by model type (closed-source, thinking-token,
    open-source). Columns report both macro and micro scores under each
    condition, plus the signed Δ. Within-group sort: no_tool macro score
    descending, so stronger baseline models are listed first. Writes CSV
    and LaTeX to ``output_dir``.
    """
    scores = compute_macro_scores(df)

    # Pivot to get no_tool and tool side by side
    pivot = scores.pivot(index="model", columns="condition",
                         values=["macro_score", "micro_score"]).reset_index()
    pivot.columns = ["_".join(c).rstrip("_") for c in pivot.columns]

    pivot["macro_delta"] = pivot["macro_score_tool"] - pivot["macro_score_no_tool"]
    pivot["micro_delta"] = pivot["micro_score_tool"] - pivot["micro_score_no_tool"]
    pivot["model_short"] = pivot["model"].map(MODEL_SHORT_NAMES)
    pivot["model_group"] = pivot["model"].map(MODEL_TO_GROUP)

    # Sort by group order, then by no_tool macro within group
    group_order = {"Closed-source": 0, "Thinking-token": 1, "Open-source": 2}
    pivot["_group_order"] = pivot["model_group"].map(group_order)
    pivot = pivot.sort_values(
        ["_group_order", "macro_score_no_tool"],
        ascending=[True, False],
    )

    # CSV
    csv_cols = ["model_short", "model_group",
                "macro_score_no_tool", "macro_score_tool", "macro_delta",
                "micro_score_no_tool", "micro_score_tool", "micro_delta"]
    csv_path = output_dir / "table1_leaderboard.csv"
    pivot[csv_cols].to_csv(csv_path, index=False, float_format="%.4f")
    print(f"Table 1 CSV: {csv_path}")

    # LaTeX — compute caption summary dynamically so it can't drift
    n_neg = (pivot["macro_delta"] < 0).sum()
    n_total = len(pivot)
    if n_neg == n_total:
        delta_desc = f"All {n_total} models show negative tool $\\Delta$"
    elif n_neg == 0:
        delta_desc = f"All {n_total} models show non-negative tool $\\Delta$"
    else:
        delta_desc = f"{n_neg}/{n_total} models show negative tool $\\Delta$"

    latex_path = output_dir / "table1_leaderboard.tex"
    with open(latex_path, "w") as f:
        f.write("\\begin{table}[t]\n")
        f.write("\\centering\n")
        f.write(f"\\caption{{Model leaderboard. Macro and micro scores by condition. "
                f"{delta_desc}.}}\n")
        f.write("\\label{tab:leaderboard}\n")
        f.write("\\small\n")
        f.write("\\begin{tabular}{llcccccc}\n")
        f.write("\\toprule\n")
        f.write("& & \\multicolumn{3}{c}{Macro Score} & \\multicolumn{3}{c}{Micro Score} \\\\\n")
        f.write("\\cmidrule(lr){3-5} \\cmidrule(lr){6-8}\n")
        f.write("Model & Type & No Tool & Tool & $\\Delta$ & No Tool & Tool & $\\Delta$ \\\\\n")
        f.write("\\midrule\n")

        prev_group = None
        for _, row in pivot.iterrows():
            group = row["model_group"]
            if prev_group is not None and group != prev_group:
                f.write("\\midrule\n")
            prev_group = group

            f.write(f"{row['model_short']} & {group} & "
                    f"{row['macro_score_no_tool']:.3f} & "
                    f"{row['macro_score_tool']:.3f} & "
                    f"{row['macro_delta']:+.3f} & "
                    f"{row['micro_score_no_tool']:.3f} & "
                    f"{row['micro_score_tool']:.3f} & "
                    f"{row['micro_delta']:+.3f} \\\\\n")

        f.write("\\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{table}\n")

    print(f"Table 1 LaTeX: {latex_path}")

    # Print
    print("\n=== Table 1: Model Leaderboard ===")
    print(f"{'Model':<22s} {'Type':<16s} {'Macro_nt':>8s} {'Macro_t':>8s} {'MΔ':>7s} "
          f"{'Micro_nt':>8s} {'Micro_t':>8s} {'mΔ':>7s}")
    print("-" * 95)
    prev_group = None
    for _, row in pivot.iterrows():
        if prev_group is not None and row["model_group"] != prev_group:
            print("-" * 95)
        prev_group = row["model_group"]
        print(f"{row['model_short']:<22s} {row['model_group']:<16s} "
              f"{row['macro_score_no_tool']:8.4f} {row['macro_score_tool']:8.4f} "
              f"{row['macro_delta']:+7.3f} "
              f"{row['micro_score_no_tool']:8.4f} {row['micro_score_tool']:8.4f} "
              f"{row['micro_delta']:+7.3f}")


def generate_table2(df, output_dir):
    """Table 2: Per-category breakdown.

    One row per model (in canonical MODEL_ORDER), one column block per
    task type containing ``no_tool / tool`` scores and Δ. The LaTeX
    variant bolds cells where Δ is positive (tool helped) to highlight
    the exceptions. Writes CSV (wide format) and LaTeX to ``output_dir``.
    """
    per_task = compute_per_task_scores(df)

    # Pivot: model × (condition × task_type)
    pivot = per_task.pivot_table(
        index="model", columns=["task_type", "condition"], values="score"
    )

    # Build flat table
    rows = []
    for model in MODEL_ORDER:
        row = {"model": model, "model_short": MODEL_SHORT_NAMES.get(model, model)}
        for task in TASK_TYPE_ORDER:
            nt = pivot.loc[model, (task, "no_tool")] if (task, "no_tool") in pivot.columns else np.nan
            t = pivot.loc[model, (task, "tool")] if (task, "tool") in pivot.columns else np.nan
            row[f"{task}_no_tool"] = nt
            row[f"{task}_tool"] = t
            row[f"{task}_delta"] = t - nt if pd.notna(nt) and pd.notna(t) else np.nan
        rows.append(row)

    result = pd.DataFrame(rows)

    # CSV
    csv_path = output_dir / "table2_per_category.csv"
    result.to_csv(csv_path, index=False, float_format="%.4f")
    print(f"\nTable 2 CSV: {csv_path}")

    # LaTeX — delta only (compact for paper)
    latex_path = output_dir / "table2_per_category.tex"
    with open(latex_path, "w") as f:
        f.write("\\begin{table*}[t]\n")
        f.write("\\centering\n")
        f.write("\\caption{Per-category scores. Each cell shows no\\_tool / tool ($\\Delta$). "
                "Bold: positive $\\Delta$ (tool helps).}\n")
        f.write("\\label{tab:per-category}\n")
        f.write("\\small\n")
        cols = "l" + "c" * len(TASK_TYPE_ORDER)
        f.write(f"\\begin{{tabular}}{{{cols}}}\n")
        f.write("\\toprule\n")
        header = "Model & " + " & ".join(TASK_TYPE_ORDER) + " \\\\\n"
        f.write(header)
        f.write("\\midrule\n")

        for _, row in result.iterrows():
            cells = [row["model_short"]]
            for task in TASK_TYPE_ORDER:
                nt = row[f"{task}_no_tool"]
                t = row[f"{task}_tool"]
                d = row[f"{task}_delta"]
                if pd.notna(d) and d > 0:
                    cells.append(f"\\textbf{{{nt:.2f} / {t:.2f}}}")
                else:
                    cells.append(f"{nt:.2f} / {t:.2f}")
            f.write(" & ".join(cells) + " \\\\\n")

        f.write("\\bottomrule\n")
        f.write(f"\\end{{tabular}}\n")
        f.write("\\end{table*}\n")

    print(f"Table 2 LaTeX: {latex_path}")

    # Print delta-only view
    print("\n=== Table 2: Per-Category Δ (tool - no_tool) ===")
    header = f"{'Model':<22s}" + "".join(f" {t:>7s}" for t in TASK_TYPE_ORDER)
    print(header)
    print("-" * len(header))
    for _, row in result.iterrows():
        line = f"{row['model_short']:<22s}"
        for task in TASK_TYPE_ORDER:
            d = row[f"{task}_delta"]
            if pd.notna(d):
                line += f" {d:+7.3f}"
            else:
                line += f" {'N/A':>7s}"
        print(line)

    # Task type averages
    print("\n--- Task Type Average Δ ---")
    for task in TASK_TYPE_ORDER:
        vals = result[f"{task}_delta"].dropna()
        print(f"  {task}: {vals.mean():+.4f} (±{vals.std():.4f}, n={len(vals)})")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate paper tables")
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--output-dir", default="results/analysis")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_all_evaluations(args.results_dir)
    generate_table1(df, output_dir)
    generate_table2(df, output_dir)


if __name__ == "__main__":
    main()
