#!/usr/bin/env python3
"""
Panels of Fig. 3 and Fig. 4b from the three-round follow-up data (results_revision/analysis/evaluations.pkl,
written by scripts/revision/analyze_revision.py). Main-text conditions: no_tool, tool (the standard tool),
graph_in_context (the whole wheel in the prompt); Fig. 4b also shows tool_resolved (the alias tool).

Each panel is written as a separate file (PDF and PNG) at its final size within a 10 x 7.5 in
figure, so fonts are their real size; panel letters are not drawn.

  Fig. 3a  score vs cost per question: no tool -> tool-augmented | no tool -> wheel-in-context
  Fig. 3b  Δ by task type, tool-augmented and wheel-in-context
  legend   shared model legend under a and b
  Fig. 3c  rejection answers: NONE on T1.1/T1.4/T1.5, "No" on T1.2
  Fig. 3d  score vs number of traversal calls (budget 5), tool condition
  Fig. 4b  T1.1 split: root named as in the wheel vs layer-labelled root, standard and alias tool

All values: mean over the three rounds. Scores 0-100 in a; 0-1 elsewhere. Cost = list price x tokens
(configs/models.yaml), per question. Error bars: b s.e.m. over the 11 models (ddof = 1); c SD over rounds.
Statistics for the caption are in fig3_values.csv.

Writes the panels and fig3_values.csv to results_revision/figures/.

Usage:  python scripts/revision/figures_fig3.py

The panels can also be drawn from Python (e.g. in a notebook). Every panel function takes the full
evaluations table (evaluations.pkl), draws the panel on a new figure of its final size (or on the
Axes/Figure passed in) and returns the values it records, as a list of {"panel", "key", "value"} rows:

    ev = pd.read_pickle("results_revision/analysis/evaluations.pkl")
    panel_3a(ev); panel_3b(ev); model_legend(ev); panel_3c(ev, questions); panel_3d(ev); panel_4b(ev)
"""

import json
import sys
from pathlib import Path

import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")      # files only; when imported (e.g. in a notebook) the caller's backend is kept
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_style import M2S, MODEL_STYLE, label  # noqa: E402

OUT = ROOT / "results_revision/figures"
DATA = ROOT / "results_revision/analysis/evaluations.pkl"
QUESTIONS = ROOT / "data/questions/benchmark_questions.json"

# panel sizes (inches) within the 10 x 7.5 in figure
SIZE = {"a": (4.95, 3.2), "b": (4.95, 3.2), "legend": (9.9, 0.42), "c": (5.0, 3.45), "d": (4.9, 3.45),
        "4b": (4.08, 2.2)}
# panel margins (inches)
MARGINS = {"a": dict(left=0.42, right=0.06, bottom=0.42, top=0.52, wspace=0.07),
           "b": dict(left=0.52, right=0.06, bottom=0.42, top=0.52),
           "4b": dict(left=0.48, right=0.06, bottom=0.55, top=0.30),
           "c": dict(left=0.48, right=0.06, bottom=0.62, top=0.42),   # top: room for the panel letter
           "d": dict(left=0.48, right=0.08, bottom=0.62, top=0.42)}
FS = {"base": 7.5, "label": 8, "tick": 7, "legend": 7, "title": 8}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": FS["base"], "axes.titlesize": FS["title"], "axes.labelsize": FS["label"],
    "xtick.labelsize": FS["tick"], "ytick.labelsize": FS["tick"], "legend.fontsize": FS["legend"],
    "xtick.direction": "in", "ytick.direction": "in", "xtick.top": False, "ytick.right": False,
    "axes.linewidth": 0.7, "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5, "lines.linewidth": 1.2,
})

CONDS = ["no_tool", "tool", "graph_in_context"]
CNAME = {"no_tool": "No tool", "tool": "Tool-augmented", "graph_in_context": "Wheel-in-context"}
CCOL = {"no_tool": "#4878CF", "tool": "#D65F5F", "graph_in_context": "#E0A030"}
TASKS = ["A1", "A2", "A3", "A4", "A5", "E1", "E2", "E3", "F"]
TLAB = dict(zip(TASKS, ["T1.1", "T1.2", "T1.3", "T1.4", "T1.5", "T2.1", "T2.2", "T2.3", "T3"]))
MS = 26           # marker area (pt^2) at final size (Fig. 3a)


def save(fig, name):
    """Fixed canvas (no tight cropping) so each image has exactly its panel size."""
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=400)
    plt.close(fig)


def inch_margins(fig, left, right, bottom, top, **kw):
    """subplots_adjust with margins given in inches."""
    w, h = fig.get_size_inches()
    fig.subplots_adjust(left=left / w, right=1 - right / w, bottom=bottom / h, top=1 - top / h, **kw)


def panel_figure(key, ncols=1, **kw):
    """A new figure of the panel's final size and margins; returns (fig, ax or array of axes)."""
    fig, ax = plt.subplots(1, ncols, figsize=SIZE[key], **kw)
    inch_margins(fig, **MARGINS[key])
    return fig, ax


def main_conditions(ev):
    """The three main-text conditions, with the models' short names (column `short`)."""
    df = ev[ev.condition.isin(CONDS)].copy()
    df["short"] = df.model.map(M2S)
    assert df.short.notna().all(), df[df.short.isna()].model.unique()
    return df


def model_summary(ev):
    """Per model and condition: macro score and strict score (0-100) and mean cost per question.

    Returns (tm, mac, cost, models):
      tm      (round, short, condition, task) -> mean score / score_strict (0-1)
      mac     (short, condition) -> macro score over the nine task types, mean over the rounds (0-100)
      cost    (short, condition) -> mean list-price cost per question (rows with a token record)
      models  short names ordered by no-tool score, best first (the legend order)
    """
    df = main_conditions(ev)
    tm = df.groupby(["round", "short", "condition", "task"])[["score", "score_strict"]].mean()
    mac = (tm.groupby(["round", "short", "condition"]).mean() * 100).groupby(["short", "condition"]).mean()
    cost = df[(df.in_tok + df.out_tok) > 0].groupby(["short", "condition"]).cost.mean()
    models = sorted(df.short.unique(), key=lambda m: -mac.loc[(m, "no_tool"), "score"])
    return tm, mac, cost, models


# ----------------------------------------------------------------------------- a

def money(x, _):
    return f"${x:.4f}" if x < 0.001 else (f"${x:.3f}" if x < 0.01 else f"${x:.2f}")


def _draw_point(ax, m, c, mac, cost):
    mk, col = MODEL_STYLE[m]
    x, y = cost[(m, c)], mac.loc[(m, c), "score"]
    if c == "no_tool":
        ax.scatter(x, y, marker=mk, s=MS, facecolors="white", edgecolors=col, linewidths=1.2, zorder=5)
    elif c == "tool":
        ax.scatter(x, y, marker=mk, s=MS, facecolors=col, edgecolors=col, linewidths=0.8, zorder=5)
    else:
        ax.plot([x], [y], marker=mk, ms=5.6, ls="none", markeredgecolor=col, markeredgewidth=1.0,
                markerfacecolor=col, markerfacecoloralt="white", fillstyle="bottom", zorder=5)
    ys = mac.loc[(m, c), "score_strict"]
    if y - ys >= 1.0:
        ax.plot([x, x], [y, ys], color=col, lw=0.6, ls=":", zorder=4, alpha=0.8)
        ax.scatter(x, ys, marker="x", s=10, color=col, linewidths=0.9, zorder=6)


def _arrow(ax, m, c, ls, mac, cost):
    col = MODEL_STYLE[m][1]
    ax.annotate("", xy=(cost[(m, c)], mac.loc[(m, c), "score"]),
                xytext=(cost[(m, "no_tool")], mac.loc[(m, "no_tool"), "score"]),
                arrowprops=dict(arrowstyle="-|>", mutation_scale=6, color=col, lw=0.9, ls=ls,
                                connectionstyle="arc3,rad=0.06", shrinkA=3.5, shrinkB=3.5), zorder=3)


def panel_3a(ev, axes=None):
    """Fig. 3a: macro score (0-100) against cost per question, no tool -> tool-augmented (left) and
    no tool -> wheel-in-context (right); crosses mark strict scores at least 1 point lower.

    ev: the evaluations table; axes: two Axes sharing y (a new figure of the panel's size if None)."""
    tm, mac, cost, models = model_summary(ev)
    values = []
    for m in models:
        for c in CONDS:
            values.append({"panel": "a", "key": f"{m}|{c}|score", "value": mac.loc[(m, c), "score"]})
            values.append({"panel": "a", "key": f"{m}|{c}|strict", "value": mac.loc[(m, c), "score_strict"]})
            values.append({"panel": "a", "key": f"{m}|{c}|cost_usd", "value": cost.loc[(m, c)]})
    if axes is None:
        fig, axes = panel_figure("a", ncols=2, sharey=True)
    fig = axes[0].figure
    for ax, c, ls, title in ((axes[0], "tool", "-", "No tool → tool-augmented"),
                             (axes[1], "graph_in_context", "--", "No tool → wheel-in-context")):
        for m in models:
            _arrow(ax, m, c, ls, mac, cost)
            _draw_point(ax, m, "no_tool", mac, cost)
            _draw_point(ax, m, c, mac, cost)
        ax.set_xscale("log")
        ax.set_xlim(5e-5, 0.08)
        ax.set_ylim(40, 68)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(money))
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.set_title(title, fontsize=FS["title"], pad=3)
    axes[0].set_ylabel("Score")
    fig.supxlabel("Cost per question (USD, log scale)", fontsize=FS["label"], y=0.015)
    fig.legend(handles=[
        Line2D([0], [0], marker="o", color="#555", markerfacecolor="white", ms=4.5, lw=0, label="No tool"),
        Line2D([0], [0], marker="o", color="#555", markerfacecolor="#555", ms=4.5, lw=0.9, label="Tool-augmented"),
        Line2D([0], [0], marker="o", color="#555", markerfacecolor="#555", markerfacecoloralt="white", fillstyle="bottom",
               ms=4.5, lw=0.9, ls="--", label="Wheel-in-context"),
        Line2D([0], [0], marker="x", color="#555", ms=4, lw=0, markeredgewidth=0.9, label="Strict score")],
        loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False, handlelength=2.0, columnspacing=1.0)
    return values


# ----------------------------------------------------------------------------- b

def panel_3b(ev, ax=None):
    """Fig. 3b: task-level Δ (condition − no tool, 0-1) per task type for the tool-augmented and
    wheel-in-context conditions; bars = mean over the 11 models (each model: mean over rounds),
    error bars = s.e.m. over models, symbols = the models."""
    tm, mac, cost, models = model_summary(ev)
    values = []
    dl = {}
    for c in ("tool", "graph_in_context"):
        x = tm.xs(c, level="condition").score - tm.xs("no_tool", level="condition").score
        dl[c] = x.groupby(["short", "task"]).mean()
    if ax is None:
        fig, ax = panel_figure("b")
    fig = ax.figure
    xs = np.arange(len(TASKS))
    w = 0.38
    rng = np.random.default_rng(0)
    for i, c in enumerate(("tool", "graph_in_context")):
        off = (-0.5 + i) * w
        mean = [dl[c].xs(t, level="task").mean() for t in TASKS]
        sem = [dl[c].xs(t, level="task").std(ddof=1) / np.sqrt(len(models)) for t in TASKS]
        ax.bar(xs + off, mean, w, color=CCOL[c], alpha=0.8, edgecolor="grey", linewidth=0.4, zorder=2, label=CNAME[c])
        ax.errorbar(xs + off, mean, yerr=sem, fmt="none", color="black", capsize=1.8, capthick=0.7, lw=0.7, zorder=3)
        for t, mu, se in zip(TASKS, mean, sem):
            values.append({"panel": "b", "key": f"{c}|{TLAB[t]}|mean", "value": mu})
            values.append({"panel": "b", "key": f"{c}|{TLAB[t]}|sem", "value": se})
        for m in models:
            mk, col = MODEL_STYLE[m]
            for ti, t in enumerate(TASKS):
                ax.scatter(ti + off + rng.uniform(-0.12, 0.12), dl[c].loc[(m, t)], marker=mk, s=6, color=col,
                           alpha=0.6, linewidths=0, zorder=4)
    ax.axhline(0, color="black", lw=0.7, zorder=1)
    ax.set_xticks(xs)
    ax.set_xticklabels([TLAB[t] for t in TASKS])
    ax.tick_params(axis="x", which="major", length=0)
    ax.set_xticks(xs[:-1] + 0.5, minor=True)
    ax.tick_params(axis="x", which="minor", length=2.5, direction="in")
    ax.set_xlim(-0.6, len(TASKS) - 0.4)
    ax.set_xlabel("Task type")
    ax.set_ylabel(r"$\Delta$ score (condition $-$ no tool)")
    ax.set_title("Effect by task type (mean ± s.e.m. across 11 models)", fontsize=FS["title"], pad=3)
    fig.legend(handles=[mpatches.Patch(color=CCOL[c], alpha=0.8, label=CNAME[c]) for c in ("tool", "graph_in_context")],
               loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False)
    return values


# ----------------------------------------------------------------------------- shared model legend (a, b)

def model_legend(ev, fig=None):
    """The model legend shared by Fig. 3a and 3b (marker and colour per model, ordered by no-tool score).
    Returns the model order (short names)."""
    models = model_summary(ev)[3]
    if fig is None:
        fig = plt.figure(figsize=SIZE["legend"])
    fig.legend(handles=[Line2D([0], [0], marker=MODEL_STYLE[m][0], color=MODEL_STYLE[m][1],
                               markerfacecolor=MODEL_STYLE[m][1], markersize=5.5, lw=0, label=label(m)) for m in models],
               loc="center", ncol=6, fontsize=FS["legend"] + 0.5, frameon=False, handletextpad=0.3, columnspacing=1.6,
               labelspacing=0.35)
    return models


# ----------------------------------------------------------------------------- Fig. 4b (T1.1 split)
# standard tool vs alias tool (code name tool_resolved: bare layer labels, benchmark spellings and word forms are
# accepted as aliases of tool-graph nodes; the graph itself is unchanged), with no tool and wheel-in-context
C4 = ["no_tool", "tool", "tool_resolved", "graph_in_context"]
N4 = {**CNAME, "tool_resolved": "Alias tool"}


def panel_4b(ev, ax=None):
    """Fig. 4b: T1.1 mean score (question means over models and rounds) for questions whose correct root
    is named as in the wheel (a1_in_graph) vs only layer-labelled (floral, green/vegetable), in four
    conditions; records Δ vs no tool and the two-sided Mann-Whitney U test of the question-level Δ."""
    values = []
    a1 = ev[(ev.task == "A1") & ev.condition.isin(C4)]
    ing = a1.drop_duplicates("question_id").set_index("question_id").a1_in_graph.astype(bool)
    q = a1.groupby(["condition", "question_id"]).score.mean()
    groups = [("exact wheel name", ing[ing].index), ("layer-labelled root", ing[~ing].index)]
    if ax is None:
        fig, ax = panel_figure("4b")
    w = 0.2
    for gi, (gname, qids) in enumerate(groups):
        base = q.loc["no_tool"].reindex(qids)
        for ci, c in enumerate(C4):
            v = q.loc[c].reindex(qids)
            alias = c == "tool_resolved"
            ax.bar(gi + (ci - 1.5) * w, v.mean(), w, color="white" if alias else CCOL[c], alpha=1 if alias else 0.85,
                   edgecolor=CCOL["tool"] if alias else "none", hatch="////" if alias else None, lw=0.8)
            values.append({"panel": "4b", "key": f"{gname}|{c}|mean_score", "value": v.mean()})
            if c != "no_tool":
                values.append({"panel": "4b", "key": f"{gname}|{c}|delta", "value": (v - base).mean()})
    for c in ("tool", "tool_resolved", "graph_in_context"):
        dq = q.loc[c] - q.loc["no_tool"]
        U, p = stats.mannwhitneyu(dq.reindex(ing[ing].index), dq.reindex(ing[~ing].index), alternative="two-sided")
        values.append({"panel": "4b", "key": f"{c}|MannWhitney_U", "value": U})
        values.append({"panel": "4b", "key": f"{c}|MannWhitney_p", "value": p})
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f"Root named as in wheel\n(n={len(groups[0][1])})",
                        f"Root layer-labelled: floral, green/veg.\n(n={len(groups[1][1])})"])
    ax.tick_params(axis="x", which="major", length=0)
    ax.set_ylabel("T1.1 mean score (F1)")
    ax.set_ylim(0, 1.15)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_title("T1.1 by root naming", pad=3)
    hand = [mpatches.Patch(facecolor="white" if c == "tool_resolved" else CCOL[c], edgecolor=CCOL["tool"] if c == "tool_resolved" else "none",
                           hatch="////" if c == "tool_resolved" else None, label=N4[c]) for c in C4]
    ax.legend(handles=hand, loc="upper center", ncol=4, frameon=False, handlelength=1.2, columnspacing=0.7, handletextpad=0.35,
              fontsize=FS["legend"] - 0.5)
    return values


# ----------------------------------------------------------------------------- c (rejection answers)

def panel_3c(ev, questions, ax=None):
    """Fig. 3c: share of rejection answers (% of evaluations; mean over rounds, error bar SD over rounds):
    NONE (column none_sel) on T1.1, T1.4, T1.5 and "No" (column said_no) on T1.2, per main condition;
    dashed line = share of questions whose correct answer is NONE / "No".

    questions: the list in data/questions/benchmark_questions.json["questions"] (for the T1.2 answer keys)."""
    df = main_conditions(ev)
    values = []
    if ax is None:
        fig, ax = panel_figure("c")
    w = 0.26
    order = [("A1", "none_sel"), ("A4", "none_sel"), ("A5", "none_sel"), ("A2", "said_no")]
    xs = np.array([0, 1, 2, 3.35])
    bq = {qq["id"]: qq for qq in questions}
    for ci, c in enumerate(CONDS):
        for x, (t, col) in zip(xs, order):
            pr = df[(df.condition == c) & (df.task == t)].groupby("round")[col].mean().astype(float) * 100
            ax.bar(x + (ci - 1) * w, pr.mean(), w, color=CCOL[c], alpha=0.85)
            ax.errorbar(x + (ci - 1) * w, pr.mean(), yerr=pr.std(ddof=1), fmt="none", color="black", capsize=1.5, lw=0.6)
            values.append({"panel": "c", "key": f"{TLAB[t]}|{c}|{col}_pct", "value": pr.mean()})
            values.append({"panel": "c", "key": f"{TLAB[t]}|{c}|sd_rounds", "value": pr.std(ddof=1)})
    for x, (t, col) in zip(xs, order):
        qids = df[df.task == t].question_id.unique()
        if col == "none_sel":
            corr = df[df.task == t].drop_duplicates("question_id").correct_is_none.mean() * 100
        else:   # T1.2: share of questions whose correct option is "No"
            corr = np.mean([bq[i]["options"][bq[i]["correct_answer"]] == "No" for i in qids]) * 100
        ax.plot([x - 1.6 * w, x + 1.6 * w], [corr] * 2, color="black", lw=0.9, ls="--", zorder=5)
        values.append({"panel": "c", "key": f"{TLAB[t]}|correct_pct", "value": corr})
    ax.plot([2.68, 2.68], [0, 104], color="grey", lw=0.5, ls=":")   # stops below the legend
    ax.set_xticks(xs)
    ax.set_xticklabels(["T1.1\n", "T1.4\nNONE", "T1.5\n", "T1.2\n“No”"])
    ax.tick_params(axis="x", which="major", length=0)
    ax.set_ylabel("Rejection answers (%)")
    ax.set_ylim(0, 118)
    ax.set_yticks(range(0, 101, 20))
    ax.set_title("NONE / “No” answers", pad=3)
    ax.legend(handles=[mpatches.Patch(color=CCOL[c], label=CNAME[c]) for c in CONDS]
              + [Line2D([0], [0], color="black", lw=0.9, ls="--", label="Correct answer rate")],
              loc="upper center", ncol=4, frameon=False, handlelength=1.4, columnspacing=0.8, handletextpad=0.4)
    return values


# ----------------------------------------------------------------------------- d (traversal calls)
D_LINES = {"A1": ("#8E44AD", "-", "D"), "A3": ("#1565C0", "-", "s"), "A4": ("#E53935", "-", "o"),
           "A5": ("#FF7043", "--", "o"), "E3": ("#2E7D32", "--", "s")}


def panel_3d(ev, ax=None):
    """Fig. 3d: mean score of tool-augmented evaluations (all rounds pooled) by number of traversal calls
    (column traversal_calls = get_parent + get_children, 5+ pooled) for T1.1, T1.3, T1.4, T1.5, T2.3;
    records the means, counts and Spearman's rho over the unbinned call counts."""
    df = main_conditions(ev)
    values = []
    if ax is None:
        fig, ax = panel_figure("d")
    tool = df[df.condition == "tool"].copy()
    tool["bucket"] = tool.traversal_calls.clip(upper=5)
    for t, (col, ls, mk) in D_LINES.items():
        s_ = tool[tool.task == t]
        g = s_.groupby("bucket").score.agg(["mean", "size"]).reindex(range(6))
        rho = stats.spearmanr(s_.traversal_calls, s_.score)
        ax.plot(range(6), g["mean"], color=col, lw=1.1, ls=ls, marker=mk, ms=3.2, label=TLAB[t], zorder=3)
        for b in range(6):
            values.append({"panel": "d", "key": f"{TLAB[t]}|traversal={b if b < 5 else '5+'}|mean", "value": g["mean"][b]})
            values.append({"panel": "d", "key": f"{TLAB[t]}|traversal={b if b < 5 else '5+'}|n", "value": g["size"][b]})
        values.append({"panel": "d", "key": f"{TLAB[t]}|spearman_rho", "value": rho.correlation})
        values.append({"panel": "d", "key": f"{TLAB[t]}|spearman_p", "value": rho.pvalue})
    ax.set_xticks(range(6))
    ax.set_xticklabels(["0", "1", "2", "3", "4", "5+"])
    ax.set_xlabel("Traversal calls (budget 5)")
    ax.set_ylabel("Mean score (tool-augmented)")
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_title("Score vs. traversal calls", pad=3)
    ax.legend(loc="upper center", ncol=5, frameon=False, handlelength=1.6, columnspacing=0.55, handletextpad=0.25,
              borderaxespad=0.2, fontsize=FS["legend"] - 0.5)
    return values


# ----------------------------------------------------------------------------- command line

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ev = pd.read_pickle(DATA)                 # Fig. 4b also uses the alias tool (tool_resolved)
    questions = json.load(open(QUESTIONS))["questions"]
    values = []

    fig, axes = panel_figure("a", ncols=2, sharey=True)
    values += panel_3a(ev, axes)
    save(fig, "fig3a")

    fig, ax = panel_figure("b")
    values += panel_3b(ev, ax)
    save(fig, "fig3b")

    fig = plt.figure(figsize=SIZE["legend"])
    model_legend(ev, fig)
    save(fig, "fig3ab_legend")

    fig, ax = panel_figure("4b")
    values += panel_4b(ev, ax)
    save(fig, "fig4b")

    fig, ax = panel_figure("c")
    values += panel_3c(ev, questions, ax)
    save(fig, "fig3c")

    fig, ax = panel_figure("d")
    values += panel_3d(ev, ax)
    save(fig, "fig3d")

    pd.DataFrame(values).to_csv(OUT / "fig3_values.csv", index=False)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
