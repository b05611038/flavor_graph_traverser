#!/usr/bin/env python3
"""
Values for the manuscript tables (Table 1, Supplementary Tables 1-5 and 8) from the three follow-up
rounds (results_revision/analysis/evaluations.pkl from analyze_revision.py), and the supplementary
table of the two control conditions (prompt_only, tool_resolved).

Conventions: scores 0-100 for macro scores, 0-1 for task Δ; "tool" is
the original tool-augmented condition. Every value is the mean over the three rounds; ± is the SD
over rounds where shown. Cost per question = list price x tokens (configs/models.yaml).

Writes results_revision/analysis/manuscript_tables.json and prints the tables.
Usage: python scripts/revision/manuscript_tables.py
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/revision"))
from analyze_revision import bh, gather, wilcoxon_rb  # noqa: E402
from judge_scores import company  # noqa: E402

OUT = ROOT / "results_revision/analysis/manuscript_tables.json"
df = pd.read_pickle(ROOT / "results_revision/analysis/evaluations.pkl")
TASKS = ["A1", "A2", "A3", "A4", "A5", "E1", "E2", "E3", "F"]
LAB = dict(zip(TASKS, ["T1.1", "T1.2", "T1.3", "T1.4", "T1.5", "T2.1", "T2.2", "T2.3", "T3"]))
# row order and display names of the manuscript tables; the two replaced models take the rows of their predecessors
ROWS = [("anthropic/claude-sonnet-4.6", "Claude Sonnet 4.6"), ("google/gemini-3-flash-preview", "Gemini 3 Flash Preview"),
        ("openai/gpt-5.4", "GPT-5.4"), ("x-ai/grok-4.20", "Grok 4.20"), ("mistralai/mistral-medium-3-5", "Mistral Medium 3.5"),
        ("openai/gpt-oss-120b", "GPT-OSS 120B"), ("qwen/qwen3.5-397b-a17b", "Qwen3.5 397B"), ("moonshotai/kimi-k2.5", "Kimi K2.5"),
        ("deepseek/deepseek-v3.2", "DeepSeek V3.2"), ("nvidia/nemotron-3-super-120b-a12b", "Nemotron 3 Super 120B"),
        ("meta-llama/llama-4-maverick", "Llama 4 Maverick")]
out = {}

tm = df.groupby(["round", "model", "condition", "task"])[["score", "score_strict"]].mean()
mac = tm.groupby(["round", "model", "condition"]).mean() * 100            # (round, model, condition)

# ------------------------------------------------------------------ Supplementary Table 1
t = []
for m, name in ROWS:
    row = {"model": name}
    for c in ("no_tool", "tool", "graph_in_context"):
        s = mac.xs((m, c), level=("model", "condition"))
        cost = df[(df.model == m) & (df.condition == c) & ((df.in_tok + df.out_tok) > 0)].cost.mean()
        row[c] = {"fix": s.score.mean(), "fix_sd": s.score.std(ddof=1), "strict": s.score_strict.mean(),
                  "strict_sd": s.score_strict.std(ddof=1), "cost": cost}
    t.append(row)
out["supp1"] = t

# ------------------------------------------------------------------ Supplementary Table 2 (tool - no_tool)
d = (tm.xs("tool", level="condition").score - tm.xs("no_tool", level="condition").score).groupby(["model", "task"]).mean()
rows, ps, rbs = [], [], []
for m, name in ROWS:
    rows.append({"model": name, **{LAB[k]: d.loc[(m, k)] for k in TASKS}})
mean = {LAB[k]: np.mean([d.loc[(m, k)] for m, _ in ROWS]) for k in TASKS}
for k in TASKS:
    W, p, rb = wilcoxon_rb([d.loc[(m, k)] for m, _ in ROWS])
    ps.append(p)
    rbs.append(rb)
out["supp2"] = {"rows": rows, "mean": mean, "p_bh": dict(zip([LAB[k] for k in TASKS], bh(ps))),
                "rank_biserial": dict(zip([LAB[k] for k in TASKS], rbs))}

# ------------------------------------------------------------------ Supplementary Table 3 (query counts, tool condition, all rounds)
# Unit: one descriptor entry in a validate_descriptors result (native tool messages and ICL TOOL_RESULT lines),
# case-sensitive, all 11 models x 3 rounds. (The counts reported for the original run used native tool messages only, i.e. 9 models.)
TERMS = ["floral", "floral (inner layer)", "floral (middle layer)", "green/vegetable", "green/vegetative",
         "green/vegetative (inner layer)", "green/vegetative (middle layer)"]
cnt, valid = Counter(), Counter()
for rnd, rec, _, origin in gather():
    cond = {"tool": "tool", "tool_rerun": "tool"}.get(rec["condition"])
    if cond != "tool" or origin == "april_copy":
        continue
    for msg in rec.get("conversation_history") or []:
        content = msg.get("content") or ""
        if msg.get("role") == "tool":
            raw = content
        elif msg.get("role") == "user" and content.startswith("TOOL_RESULT:"):
            raw = content.split("TOOL_RESULT:", 1)[1].strip()
        else:
            continue
        try:
            res = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(res, dict) and ("valid" in res or "invalid" in res):
            for x in res.get("valid") or []:
                cnt[x] += 1
                valid[x] += 1
            for x in res.get("invalid") or []:
                cnt[x] += 1
out["supp3"] = {k: {"total": cnt[k], "valid": valid[k]} for k in TERMS}

# ------------------------------------------------------------------ Table 1 and Supplementary Table 5 (T3, tool - no_tool)
f = df[df.task == "F"]
ft = f[f.condition == "tool"].set_index(["round", "model", "question_id"])
fn = f[f.condition == "no_tool"].set_index(["round", "model", "question_id"])
x = pd.DataFrame({"delta": ft.score - fn.score.reindex(ft.index), "called": ft.calls > 0}).reset_index()
out["table1"] = [{"question": q, "mean": g.delta.mean(), "called_mean": g[g.called].delta.mean() if g.called.any() else None,
                  "n_called": int(g.called.sum()), "nocall_mean": g[~g.called].delta.mean() if (~g.called).any() else None,
                  "n_nocall": int((~g.called).sum())} for q, g in x.groupby("question_id")]
out["supp5"] = [{"model": name, "calls_of_45": int(x[x.model == m].called.sum()),
                 "called_mean": x[(x.model == m) & x.called].delta.mean() if x[(x.model == m) & x.called].size else None,
                 "nocall_mean": x[(x.model == m) & ~x.called].delta.mean() if x[(x.model == m) & ~x.called].size else None}
                for m, name in ROWS]

# ------------------------------------------------------------------ Supplementary Table 4 (judges, unique answers)
j = df[(df.task == "F") & (df.origin != "april_copy")].dropna(subset=["j_anthropic", "j_google", "j_openai"])
from sklearn.metrics import cohen_kappa_score  # noqa: E402
import krippendorff  # noqa: E402
R = j[["j_anthropic", "j_google", "j_openai"]].values.astype(float)
n, k = R.shape
grand = R.mean()
ss_r = k * ((R.mean(1) - grand) ** 2).sum()
ss_c = n * ((R.mean(0) - grand) ** 2).sum()
ss_e = ((R - grand) ** 2).sum() - ss_r - ss_c
msr, mse = ss_r / (n - 1), ss_e / ((n - 1) * (k - 1))
spread = R.max(1) - R.min(1)
out["supp4"] = {
    "n": int(n),
    "judges": {c: {"mean": float(j[c].mean()), "sd": float(j[c].std(ddof=1))} for c in ("j_anthropic", "j_google", "j_openai")},
    "kappa": {f"{a}|{b}": float(cohen_kappa_score(j[a].astype(int), j[b].astype(int), weights="quadratic"))
              for a, b in (("j_anthropic", "j_google"), ("j_anthropic", "j_openai"), ("j_openai", "j_google"))},
    "alpha_interval": float(krippendorff.alpha(reliability_data=R.T, level_of_measurement="interval")),
    "icc3k": float((msr - mse) / msr),
    "exact": float((spread == 0).mean()), "within1_only": float((spread == 1).mean()),
    "within2_only": float((spread == 2).mean()), "ge3": float((spread >= 3).mean()), "within1": float((spread <= 1).mean()),
}

# ------------------------------------------------------------------ supplementary table of the control conditions
ctrl = {}
for c in ("no_tool", "prompt_only", "tool", "tool_resolved", "graph_in_context"):
    sub = df[df.condition == c]
    r = {}
    for task, col in (("A1", "none_sel"), ("A4", "none_sel"), ("A5", "none_sel"), ("A2", "said_no")):
        pr = sub[sub.task == task].groupby("round")[col].mean().astype(float) * 100
        r[f"{LAB[task]}_{col}"] = (pr.mean(), pr.std(ddof=1))
    for task in T1 if (T1 := ["A1", "A2", "A3", "A4", "A5"]) else []:
        dd = (tm.xs(c, level="condition").score - tm.xs("no_tool", level="condition").score).xs(task, level="task")
        pm = dd.groupby("model").mean()
        r[f"{LAB[task]}_delta"] = (pm.mean(), dd.groupby("round").mean().std(ddof=1))
    t1 = (tm.xs(c, level="condition").score.unstack("task")[["A1", "A2", "A3", "A4", "A5"]].mean(1) * 100)
    r["T1_score"] = (t1.groupby("round").mean().mean(), t1.groupby("round").mean().std(ddof=1))
    ctrl[c] = r
po = df[df.condition == "prompt_only"]
clean = po[po.po_flags.fillna("") == ""]
ctrl["prompt_only_unflagged"] = {f"{LAB[t]}_{col}": (clean[clean.task == t][col].mean() * 100, None)
                                 for t, col in (("A1", "none_sel"), ("A4", "none_sel"), ("A5", "none_sel"), ("A2", "said_no"))}
ctrl["prompt_only_flag_share"] = float((po.po_flags.fillna("") != "").mean())
out["controls"] = ctrl

# ------------------------------------------------------------------ Supplementary Table 10 (score by condition and task, with variation)
MAIN = ("no_tool", "tool", "graph_in_context")
s10 = {"task": {}, "aggregate": {}, "repeat": {}}
for c in MAIN:
    x10 = tm.xs(c, level="condition").score.groupby(["round", "task"]).mean()          # model mean per round and task
    for k in TASKS:
        pr = x10.xs(k, level="task")
        s10["task"][f"{c}|{LAB[k]}"] = (pr.mean(), pr.std(ddof=1))
    for name, ts in (("T1", ["A1", "A2", "A3", "A4", "A5"]), ("T2", ["E1", "E2", "E3"]), ("T3", ["F"]), ("Overall", TASKS)):
        pr = (tm.xs(c, level="condition").score.unstack("task")[ts].mean(1) * 100).groupby("round").mean()
        s10["aggregate"][f"{c}|{name}"] = (pr.mean(), pr.std(ddof=1))
    sub = df[(df.condition == c) & (df.task != "F")]
    g = sub.groupby(["model", "question_id"])
    sd = tm.xs(c, level="condition").score.groupby(["model", "task"]).std(ddof=1).groupby("task").mean()
    s10["repeat"][c] = {"same_answer": float((g.answer.nunique() == 1).mean() * 100),
                        "mean_sd": float(sd.mean())}
out["supp10"] = s10

# ------------------------------------------------------------------ Supplementary Table 11 (leave-own-company-out)
fj = df[(df.task == "F") & df.condition.isin(["no_tool", "tool"])]
s11 = []
for m, name in ROWS:
    if company(m) not in ("anthropic", "google", "openai"):
        continue
    g = fj[fj.model == m].groupby(["condition", "round"])[["score", "score_loo"]].mean().groupby("condition").mean()
    s11.append({"model": name, "judge": {"anthropic": "Claude Opus 5.5", "google": "Gemini 4 Argon", "openai": "GPT-6.2 Sol"}[company(m)],
                "no_tool": g.loc["no_tool", "score"], "no_tool_loo": g.loc["no_tool", "score_loo"],
                "tool": g.loc["tool", "score"], "tool_loo": g.loc["tool", "score_loo"]})
jj = df[(df.task == "F") & (df.origin != "april_copy")].dropna(subset=["j_anthropic", "j_google", "j_openai"]).copy()
jj["company"] = jj.model.map(company)
pref = []
for jc, jname in (("j_anthropic", "Claude Opus 5.5"), ("j_google", "Gemini 4 Argon"), ("j_openai", "GPT-6.2 Sol")):
    others = [o for o in ("j_anthropic", "j_google", "j_openai") if o != jc]
    diff = jj[jc] - jj[others].mean(1)
    own = jj.company == jc[2:]
    pref.append({"judge": jname, "own": float(diff[own].mean()), "n_own": int(own.sum()), "other": float(diff[~own].mean()),
                 "p": float(stats.mannwhitneyu(diff[own], diff[~own], alternative="two-sided").pvalue)})
out["supp11"] = {"models": s11, "preference": pref}

json.dump(out, open(OUT, "w"), indent=1, default=lambda o: None if o is None or (isinstance(o, float) and np.isnan(o)) else float(o))
print(json.dumps(out, indent=1, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else float(o))[:6000])
