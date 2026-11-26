#!/usr/bin/env python3
"""
Full analysis of the follow-up runs (three rounds, five conditions, 11 models).

Stage 1 (assemble) builds one row per evaluation:
    round, model, condition, question_id, task, scores, answer flags, tool calls, tokens
  Round 1 for the 9 April models reuses the April run:
    no_tool, tool        April (results_revision/run1/original_run.json)
    tool_resolved        the 1,010 affected evaluations re-run (results_revision/run1), the
                         rest copied from the April tool transcript (unchanged by the fix)
    Nemotron tool, tool_resolved: the fresh round-1 run (results_revision/run1_nemotron_tool)
  Everything else and rounds 2-3: results_revision/run<N>/*/cache.
  Condition names: tool_rerun -> tool, prompt_only_noaccess -> prompt_only.

Scores
  score         the main score ("fixed"): parser layers 1-3 (April's stored answers
                already carry the accepted fallback parses; recomputing reproduces the
                published raw scores exactly)
  score_strict  only the canonical "I select (...)" ending counts (reproduces April's strict
                scores exactly: 6,050/6,050)
  T3            mean of the three follow-up judges / 5 (scripts/revision/judge_scores.py);
                loo = without the judge from the evaluated model's own company

Stage 2 (report) writes results_revision/analysis/report.md and CSVs.

Usage:
    python scripts/revision/analyze_revision.py            # assemble (cached) + report
    python scripts/revision/analyze_revision.py --rebuild  # re-assemble from the raw files
"""

import argparse
import csv
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/revision"))

from FlavorGraphTraverser import CoffeeDescriptionGraph, load_graph_data  # noqa: E402
from FlavorGraphTraverser.evaluation.tools import build_executor  # noqa: E402
from FlavorGraphTraverser.evaluation.utils.answer_parser import compute_question_score  # noqa: E402
from judge_scores import company, load_scores  # noqa: E402
from prompt_only_flags import classify as classify_prompt_only  # noqa: E402
from select_rerun_pairs import classify_record  # noqa: E402

OUT = ROOT / "results_revision/analysis"
APRIL_MODELS = (
    "anthropic/claude-sonnet-4.6", "openai/gpt-5.4", "google/gemini-3-flash-preview",
    "openai/gpt-oss-120b", "qwen/qwen3.5-397b-a17b", "moonshotai/kimi-k2.5",
    "meta-llama/llama-4-maverick", "deepseek/deepseek-v3.2", "nvidia/nemotron-3-super-120b-a12b")
NEW_MODELS = ("x-ai/grok-4.20", "mistralai/mistral-medium-3-5")
MODELS = APRIL_MODELS + NEW_MODELS
NEMOTRON = "nvidia/nemotron-3-super-120b-a12b"
COND = {"no_tool": "no_tool", "tool": "tool", "tool_rerun": "tool", "tool_resolved": "tool_resolved",
        "prompt_only_noaccess": "prompt_only", "graph_in_context": "graph_in_context"}
CONDS = ["no_tool", "prompt_only", "tool", "tool_resolved", "graph_in_context"]
TASKS = ["A1", "A2", "A3", "A4", "A5", "E1", "E2", "E3", "F"]
T1 = ["A1", "A2", "A3", "A4", "A5"]
LABEL = {"A1": "T1.1", "A2": "T1.2", "A3": "T1.3", "A4": "T1.4", "A5": "T1.5",
         "E1": "T2.1", "E2": "T2.2", "E3": "T2.3", "F": "T3"}
TYPE = {**{t: "T1" for t in T1}, "E1": "T2", "E2": "T2", "E3": "T2", "F": "T3"}
# strict score: only the canonical "Therefore, I select (...)" ending counts, whether it is found in the visible
# response or (when the response is cut off) in the reasoning trace; the original run's parser labelled the latter
# "[from thinking_content]", the current parser "[thinking]"
CANONICAL = {"I select (X)", "I select (...)", "I select (...) (NONE)", "I select (X) [from thinking_content]",
             "I select (X) [thinking]", "I select (...) [thinking]", "I select (...) (NONE) [thinking]"}
LAYERED_ROOTS = {"floral", "green/vegetable"}
SHORT = {m: m.split("/")[1] for m in MODELS}


# ----------------------------------------------------------------------------- stage 1

def is_none(answer):
    return answer == [] or answer == ["NONE"] or answer == "NONE"


def pricing():
    cfg = yaml.safe_load(open(ROOT / "configs/models.yaml"))
    return {m["id"]: m["pricing"] for k in ("closed_source", "open_source") for m in cfg[k]}


def question_meta():
    qs = json.load(open(ROOT / "data/questions/benchmark_questions.json"))["questions"]
    wheel = set(json.load(open(ROOT / "data/graphs/coffee_flavor_wheel.json"))["descriptions"])
    meta = {}
    for q in qs:
        opts = q.get("options") or {}
        ca = q.get("correct_answer")
        ca = [c.strip() for c in ca.split(",")] if isinstance(ca, str) else list(ca or [])
        task = q["id"].split("_")[0]
        m = {"no_key": next((k for k, v in opts.items() if v == "No"), None),
             "correct_is_none": task in ("A1", "A4", "A5") and (not ca or ca == ["NONE"])}
        if task == "A1":
            m["a1_in_graph"] = all(opts[c] in wheel for c in ca if c in opts)
        if task == "A4":
            m["a4_layered"] = any(opts[c].split(" > ")[0].strip() in LAYERED_ROOTS for c in ca if c in opts)
        meta[q["id"]] = m
    return meta


def caches(run_dir):
    return sorted(glob.glob(str(ROOT / run_dir / "*/cache/**/*.json"), recursive=True))


def gather():
    """[(round, record, judge_key, origin)]"""
    items = []
    april = [r for r in json.load(open(ROOT / "results_revision/run1/original_run.json"))["results"] if r["model"] in APRIL_MODELS]
    pairs = {(r["model"], r["question_id"]) for r in csv.DictReader(open(ROOT / "results_revision/rerun_pairs.csv"))
             if r["purpose"] == "label_fix"}
    for r in april:
        key = ("april", r["model"], r["condition"], r["question_id"])
        if r["condition"] == "no_tool":
            items.append((1, r, key, "april"))
        elif r["condition"] == "tool" and r["model"] != NEMOTRON:
            items.append((1, r, key, "april"))
            if (r["model"], r["question_id"]) not in pairs:
                items.append((1, {**r, "condition": "tool_resolved"}, key, "april_copy"))
    rerun_seen = set()
    for f in caches("results_revision/run1"):
        r = json.loads(Path(f).read_text())
        assert (r.get("run_meta") or {}).get("run_tag", "").startswith("rev-run1-"), f
        if r["model"] == NEMOTRON and r["condition"] in ("tool_rerun", "tool_resolved"):
            continue
        if r["model"] in APRIL_MODELS and r["condition"] == "tool_resolved":
            rerun_seen.add((r["model"], r["question_id"]))
        items.append((1, r, ("run1", r["model"], r["condition"], r["question_id"]), "run1"))
    missing = {p for p in pairs if p[0] != NEMOTRON} - rerun_seen
    assert not missing, f"affected evaluations without a round-1 rerun: {len(missing)}"
    for f in caches("results_revision/run1_nemotron_tool"):
        r = json.loads(Path(f).read_text())
        assert (r.get("run_meta") or {}).get("run_tag", "").startswith("rev-run1-nemotron"), f
        items.append((1, r, ("run1_nemotron_tool", r["model"], r["condition"], r["question_id"]), "run1_nemotron"))
    for n in (2, 3):
        for f in caches(f"results_revision/run{n}"):
            r = json.loads(Path(f).read_text())
            assert (r.get("run_meta") or {}).get("run_tag", "").startswith(f"rev-run{n}-"), f
            items.append((n, r, (f"run{n}", r["model"], r["condition"], r["question_id"]), f"run{n}"))
    return items


def assemble():
    meta = question_meta()
    price = pricing()
    judged = load_scores()
    data = load_graph_data(str(ROOT / "data/graphs/coffee_flavor_wheel.json"))
    graph = CoffeeDescriptionGraph(data["descriptions"], data["connections"], root=data["root"])
    exact = build_executor(graph, {"label_resolution": "exact"})
    resolved = build_executor(graph, {"label_resolution": "resolve"})
    rows, seen = [], set()
    for rnd, r, jkey, origin in gather():
        cond = COND[r["condition"]]
        q, m = r["question_id"], r["model"]
        key = (rnd, m, cond, q)
        if key in seen:
            raise SystemExit(f"duplicate evaluation {key}")
        seen.add(key)
        task = q.split("_")[0]
        status = r.get("status")
        api_err = status == "api_error" or any((e or {}).get("type") == "api_error" for e in r.get("errors") or [])
        mt = r.get("metrics") or {}
        pm = (r.get("parse_result") or {}).get("pattern_matched")
        row = {"round": rnd, "model": m, "condition": cond, "question_id": q, "task": task, "origin": origin,
               "status": status, "api_error": api_err, "pattern": pm,
               "calls": (mt.get("validation_calls") or 0) + (mt.get("reasoning_calls") or 0),
               "traversal_calls": mt.get("reasoning_calls") or 0,
               "in_tok": mt.get("input_tokens") or 0, "out_tok": mt.get("output_tokens") or 0}
        p = price[m]
        row["cost"] = row["in_tok"] * p["input"] / 1e6 + row["out_tok"] * p["output"] / 1e6
        if task == "F":
            j = judged.get(jkey)
            row["judged"] = j is not None and j["complete"]
            row["score"] = row["score_strict"] = j["score"] if j else 0.0
            row["score_loo"] = (j["loo_mean"] / 5.0) if j and j["loo_mean"] is not None else row["score"]
            for jid, s in (j["judges"].items() if j else []):
                row["j_" + company(jid)] = s
            row["answer"] = None
        else:
            sc = compute_question_score(model_answer=r.get("model_answer"), correct_answer=r.get("correct_answer"),
                                        is_correct=r.get("is_correct"), status=status)
            row["score"] = sc
            row["score_strict"] = sc if pm in CANONICAL else 0.0
            ans = r.get("model_answer")
            row["answer"] = json.dumps(sorted(ans) if isinstance(ans, list) else ans)
            ok = status not in ("parse_error", "api_error")
            if task in ("A1", "A4", "A5"):
                row["none_sel"] = bool(ok and is_none(ans))
                row["none_legacy"] = ans in (None, [], "NONE", ["NONE"])   # the April notebook's definition
            if task == "A2":
                row["said_no"] = bool(ok and ans == meta[q]["no_key"])
        row["correct_is_none"] = meta[q]["correct_is_none"]
        row["a1_in_graph"] = meta[q].get("a1_in_graph")
        row["a4_layered"] = meta[q].get("a4_layered")
        if cond == "prompt_only":
            kinds, _ = classify_prompt_only(r)
            row["po_flags"] = "|".join(sorted(kinds))
        if cond in ("tool", "tool_resolved"):
            _, n_changed, cats = classify_record(r, exact, resolved)
            row["fix_categories"] = "|".join(sorted(cats))
        rows.append(row)
    df = pd.DataFrame(rows)
    return df


def check_counts(df):
    n = df.groupby(["round", "model", "condition"]).size()
    want = {c: (180 if c == "prompt_only" else 275) for c in CONDS}
    bad = [(k, v) for k, v in n.items() if v != want[k[2]]]
    expected_cells = 3 * len(MODELS) * len(CONDS)
    return n, bad, expected_cells - len(n)


# ----------------------------------------------------------------------------- stage 2 helpers

def bh(p):
    p = np.asarray(p, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    prev = 1.0
    for i, idx in enumerate(order[::-1]):
        rank = len(p) - i
        prev = min(prev, p[idx] * len(p) / rank)
        adj[idx] = prev
    return adj


def wilcoxon_rb(d):
    """two-sided Wilcoxon signed-rank on d (zeros dropped), matched-pairs rank-biserial (Kerby)."""
    d = np.asarray([x for x in d if abs(x) > 1e-12])
    if len(d) < 2:
        return np.nan, np.nan, np.nan
    res = stats.wilcoxon(d)
    ranks = stats.rankdata(np.abs(d))
    rb = (ranks[d > 0].sum() - ranks[d < 0].sum()) / ranks.sum()
    return res.statistic, res.pvalue, rb


def task_means(df, score="score"):
    """(round, model, condition, task) -> mean score"""
    return df.groupby(["round", "model", "condition", "task"])[score].mean()


def macro(tm, tasks=TASKS):
    """(round, model, condition) -> macro score 0-100 over `tasks`"""
    t = tm[tm.index.get_level_values("task").isin(tasks)]
    return t.groupby(["round", "model", "condition"]).mean() * 100


def fmt(x, nd=1):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def pm(mu, sd, nd=1):
    return f"{fmt(mu, nd)} ± {fmt(sd, nd)}"


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ----------------------------------------------------------------------------- stage 2

def report(df, models, title):
    L = []
    add = L.append
    d = df[df.model.isin(models)]
    tm = task_means(d)
    tms = task_means(d, "score_strict")
    nm = len(models)

    # --- 1. scores per model and condition
    mac = macro(tm)
    mac_s = macro(tms)
    mac_t1 = macro(tm, T1)
    add(f"## 1. Benchmark score per model and condition (0–100, macro over 9 task types; mean ± SD over 3 rounds)\n")
    add("prompt_only covers T1 only, so its column is the T1 macro score; the T1 macro of every condition is in 1b.\n")
    rows = []
    for m in models:
        r = [SHORT[m]]
        for c in CONDS:
            s = (mac_t1 if c == "prompt_only" else mac).xs((m, c), level=("model", "condition"))
            r.append(pm(s.mean(), s.std(ddof=1)))
        s1, s2 = mac.xs((m, "no_tool"), level=("model", "condition")), mac_s.xs((m, "no_tool"), level=("model", "condition"))
        t1, t2 = mac.xs((m, "tool"), level=("model", "condition")), mac_s.xs((m, "tool"), level=("model", "condition"))
        r += [fmt((s2 - s1).mean()), fmt((t2 - t1).mean())]
        rows.append(r)
    add(md_table(["model", *CONDS, "strict−fixed no_tool", "strict−fixed tool"], rows))
    add("\n### 1b. T1 / T2 / T3 aggregate per condition (0–100; model mean of the type's task-macro, ± SD over rounds; ± s.e.m. over models)\n")
    rows = []
    for c in CONDS:
        r = [c]
        for ty, ts in (("T1", T1), ("T2", ["E1", "E2", "E3"]), ("T3", ["F"]), ("all", TASKS)):
            if c == "prompt_only" and ty != "T1":
                r.append("—")
                continue
            mm = macro(tm, ts).xs(c, level="condition")            # (round, model)
            per_round = mm.groupby("round").mean()
            per_model = mm.groupby("model").mean()
            r.append(f"{fmt(per_round.mean())} ± {fmt(per_round.std(ddof=1))} (sem {fmt(per_model.std(ddof=1) / np.sqrt(nm))})")
        rows.append(r)
    add(md_table(["condition", "T1", "T2", "T3", "overall"], rows))

    # --- 2. macro Δ per model and sign test
    add("\n## 2. Tool effect per model: macro Δ vs no_tool (0–100; mean ± SD over rounds)\n")
    rows, signs = [], defaultdict(list)
    for m in models:
        r = [SHORT[m]]
        for c in ["tool", "tool_resolved", "graph_in_context"]:
            dlt = mac.xs((m, c), level=("model", "condition")) - mac.xs((m, "no_tool"), level=("model", "condition"))
            r.append(pm(dlt.mean(), dlt.std(ddof=1)) + ("" if (np.sign(dlt) == np.sign(dlt.iloc[0])).all() else " *"))
            signs[c].append(dlt)
        dlt = mac_t1.xs((m, "prompt_only"), level=("model", "condition")) - mac_t1.xs((m, "no_tool"), level=("model", "condition"))
        r.append(pm(dlt.mean(), dlt.std(ddof=1)))
        signs["prompt_only (T1)"].append(dlt)
        rows.append(r)
    add(md_table(["model", "tool", "tool_resolved", "graph_in_context", "prompt_only (T1 macro)"], rows))
    add("\n`*` = the sign of Δ differs between rounds.\n")
    rows = []
    for c, lst in signs.items():
        means = np.array([s.mean() for s in lst])
        neg = int((means < 0).sum())
        k = max(neg, nm - neg)
        p = stats.binomtest(k, nm, 0.5).pvalue if nm else np.nan
        per_round = [int((np.array([s.loc[rr] for s in lst]) < 0).sum()) for rr in (1, 2, 3)]
        rows.append([c, f"{fmt(means.mean())} ({fmt(means.min())} to {fmt(means.max())})", f"{neg}/{nm}", fmt(p, 4),
                     " / ".join(f"{x}/{nm}" for x in per_round)])
    add(md_table(["condition", "mean Δ (range over models)", "models with Δ<0 (round mean)", "sign test p (two-sided)", "Δ<0 in round 1 / 2 / 3"], rows))

    # --- 3. per-task Δ
    add("\n## 3. Δ by task type (0–1 scale; model-level Δ averaged over rounds; Wilcoxon over models, BH within each comparison)\n")
    comparisons = [("tool", "no_tool"), ("tool_resolved", "no_tool"), ("graph_in_context", "no_tool"),
                   ("prompt_only", "no_tool"), ("tool", "prompt_only"), ("tool_resolved", "tool"),
                   ("graph_in_context", "tool_resolved"), ("graph_in_context", "tool")]
    task_rows = []
    for a, b in comparisons:
        tasks = T1 if "prompt_only" in (a, b) else TASKS
        res = []
        for t in tasks:
            x = tm.xs((a, t), level=("condition", "task")) - tm.xs((b, t), level=("condition", "task"))  # (round, model)
            per_model = x.groupby("model").mean()
            per_round = x.groupby("round").mean()
            W, p, rb = wilcoxon_rb(per_model.values)
            cons = (np.sign(per_round) == np.sign(per_round.mean())).all()
            res.append([t, per_model.mean(), per_model.std(ddof=1) / np.sqrt(nm), per_round.std(ddof=1),
                        list(per_round.round(3)), cons, W, p, rb])
        adj = bh([r[7] for r in res])
        add(f"\n### {a} − {b}\n")
        rows = []
        for r, pa in zip(res, adj):
            rows.append([LABEL[r[0]], fmt(r[1], 3), fmt(r[2], 3), fmt(r[3], 3), " / ".join(f"{v:+.3f}" for v in r[4]),
                         "yes" if r[5] else "no", fmt(r[6], 1), fmt(r[7], 4), fmt(pa, 4), fmt(r[8], 2)])
            task_rows.append({"comparison": f"{a}-{b}", "task": LABEL[r[0]], "mean_delta": r[1], "sem_models": r[2],
                              "sd_rounds": r[3], "round1": r[4][0], "round2": r[4][1], "round3": r[4][2],
                              "same_sign_all_rounds": r[5], "W": r[6], "p": r[7], "p_bh": pa, "rank_biserial": r[8]})
        add(md_table(["task", "mean Δ", "s.e.m. (models)", "SD (rounds)", "round 1 / 2 / 3", "same sign", "W", "p", "p (BH)", "rank-biserial"], rows))
        for ty, ts in (("T1", T1), ("T2", ["E1", "E2", "E3"]), ("T3", ["F"])):
            if not set(ts) <= set(tasks):
                continue
            x = (macro(tm, ts).xs(a, level="condition") - macro(tm, ts).xs(b, level="condition")) / 100
            pmod, pr = x.groupby("model").mean(), x.groupby("round").mean()
            W, p, rb = wilcoxon_rb(pmod.values)
            add(f"- {ty} aggregate Δ: {pmod.mean():+.3f} (s.e.m. {pmod.std(ddof=1) / np.sqrt(nm):.3f}; rounds "
                f"{' / '.join(f'{v:+.3f}' for v in pr)}; Wilcoxon p = {p:.4f}, rank-biserial {rb:.2f})")
    pd.DataFrame(task_rows).to_csv(OUT / f"task_delta_{title}.csv", index=False)

    # --- 4. NONE and "No" rates
    add("\n## 4. NONE selection (T1.1/T1.4/T1.5) and \"No\" (T1.2), % of evaluations (mean ± SD over rounds)\n")
    rows = []
    for c in CONDS:
        r = [c]
        for t, col in (("A1", "none_sel"), ("A4", "none_sel"), ("A5", "none_sel"), ("A2", "said_no")):
            s = d[(d.condition == c) & (d.task == t)].groupby("round")[col].mean() * 100
            r.append(pm(s.mean(), s.std(ddof=1)))
        rows.append(r)
    base = [d[(d.task == t)].drop_duplicates("question_id").correct_is_none.mean() * 100 for t in ("A1", "A4", "A5")]
    a2 = d[d.task == "A2"].drop_duplicates("question_id")
    rows.append(["correct answer", fmt(base[0]), fmt(base[1]), fmt(base[2]), "(see question file)"])
    add(md_table(["condition", "T1.1 NONE", "T1.4 NONE", "T1.5 NONE", "T1.2 No"], rows))
    po = d[(d.condition == "prompt_only")]
    clean = po[po.po_flags.fillna("") == ""]
    add(f"\nprompt_only: {100 * (po.po_flags.fillna('') != '').mean():.1f}% of evaluations flagged (tool-acting / no final answer); "
        f"flags: {dict(Counter(f for s in po.po_flags.fillna('') for f in s.split('|') if f))}")
    rows = []
    for t, col in (("A1", "none_sel"), ("A4", "none_sel"), ("A5", "none_sel"), ("A2", "said_no")):
        rows.append([LABEL[t], fmt(po[po.task == t][col].mean() * 100), fmt(clean[clean.task == t][col].mean() * 100),
                     str(len(clean[clean.task == t]))])
    add(md_table(["task", "prompt_only all (%)", "unflagged only (%)", "n unflagged"], rows))
    leg = d[(d["round"] == 1) & d.task.isin(["A4", "A5"]) & d.condition.isin(["no_tool", "tool"])]
    add("\nDefinition check (round 1): NONE counted only on a parsed answer vs the April notebook's definition "
        "(None / empty / NONE, which also counts unparsed answers): "
        + "; ".join(f"{LABEL[t]} {c}: {g.none_sel.mean() * 100:.1f}% vs {g.none_legacy.mean() * 100:.1f}%"
                    for (t, c), g in leg.groupby(["task", "condition"])))

    # --- 5. T1.1 split
    add("\n## 5. T1.1 split by whether the correct root category is a tool-graph node (Δ vs no_tool, 0–1; question-level, averaged over models and rounds)\n")
    rows = []
    a1 = d[d.task == "A1"]
    nt = a1[a1.condition == "no_tool"].groupby("question_id").score.mean()
    for c in ["prompt_only", "tool", "tool_resolved", "graph_in_context"]:
        dq = a1[a1.condition == c].groupby("question_id").score.mean() - nt
        ing = a1.drop_duplicates("question_id").set_index("question_id").a1_in_graph
        x, y = dq[ing[dq.index].astype(bool)], dq[~ing[dq.index].astype(bool)]
        U, p = stats.mannwhitneyu(x, y, alternative="two-sided")
        rows.append([c, f"{x.mean():+.3f} (n={len(x)})", f"{y.mean():+.3f} (n={len(y)})", fmt(U, 1), fmt(p, 4)])
    add(md_table(["condition", "root in tool graph", "root not in tool graph (floral / green/vegetable)", "Mann-Whitney U", "p"], rows))

    # --- 6. T1.4 layered split
    add("\n## 6. T1.4 split: correct path rooted at floral or green/vegetable vs other (Δ vs no_tool, 0–100 scale)\n")
    a4 = d[d.task == "A4"]
    nt4 = a4[a4.condition == "no_tool"].groupby(["round", "model", "question_id"]).score.mean()
    rows = []
    for c in ["prompt_only", "tool", "tool_resolved", "graph_in_context"]:
        for label, sub in (("all", a4[a4.condition == c]),
                           ("excl. word-form", a4[(a4.condition == c) & ~a4.fix_categories.fillna("").str.contains("word_form")])):
            if label != "all" and c != "tool_resolved":
                continue
            s = sub.set_index(["round", "model", "question_id"]).score
            dl = (s - nt4.reindex(s.index)).rename("score").reset_index()
            dl["layered"] = dl.question_id.map(a4.drop_duplicates("question_id").set_index("question_id").a4_layered).astype(bool)
            g = dl.groupby("layered")["score"].mean() * 100
            per_round = dl.groupby(["round", "layered"])["score"].mean().unstack() * 100
            rows.append([c + ("" if label == "all" else f" ({label})"), f"{g.get(True, np.nan):+.1f}", f"{g.get(False, np.nan):+.1f}",
                         " / ".join(f"{a:+.1f} vs {b:+.1f}" for a, b in zip(per_round[True], per_round[False]))])
    add(md_table(["condition", "floral/green-rooted", "other", "round 1 / 2 / 3"], rows))
    add(f"\nQuestions: {int(a4.drop_duplicates('question_id').a4_layered.sum())} floral/green-rooted, "
        f"{int((~a4.drop_duplicates('question_id').a4_layered.astype(bool)).sum())} other.")
    tr = d[d.condition == "tool_resolved"]
    cats = Counter(c for s in tr.fix_categories.fillna("") for c in s.split("|") if c)
    add(f"\ntool_resolved evaluations using each fix category (any call): {dict(cats)} of {len(tr)}")

    # --- 7. calls gradient
    add("\n## 7. Score by number of tool calls (validate + traversal), 0–100\n")
    for c in ["tool", "tool_resolved"]:
        sub = d[d.condition == c].copy()
        sub["bucket"] = sub.calls.clip(upper=3).map({0: "0", 1: "1", 2: "2", 3: "3+"})
        tab = sub[sub.task.isin(["A3", "A4", "A5", "E3"])].groupby(["task", "bucket"]).score.agg(["mean", "size"])
        rows = []
        for t in ["A3", "A4", "A5", "E3"]:
            rows.append([LABEL[t]] + [f"{tab.loc[(t, b), 'mean'] * 100:.1f} (n={tab.loc[(t, b), 'size']})" if (t, b) in tab.index else "—"
                                      for b in ["0", "1", "2", "3+"]])
        zero = (sub.calls == 0).groupby(sub.model).mean() * 100
        add(f"\n### {c}\n")
        add(md_table(["task", "0 calls", "1", "2", "3+"], rows))
        add("\nShare of evaluations with zero tool calls by model (%): " + ", ".join(f"{SHORT[m]} {zero.get(m, 0):.0f}" for m in models))

    # --- 8. T3 per question
    add("\n## 8. T3 per question: Δ (tool − no_tool, 0–1), averaged over models and rounds; split by whether the model called a tool\n")
    f = d[d.task == "F"]
    ft = f[f.condition == "tool"].set_index(["round", "model", "question_id"])
    fn = f[f.condition == "no_tool"].set_index(["round", "model", "question_id"])
    x = pd.DataFrame({"delta": ft.score - fn.score.reindex(ft.index), "called": ft.calls > 0}).reset_index()
    rows = []
    for q, g in x.groupby("question_id"):
        pr = g.groupby("round").delta.mean()
        rows.append([q, f"{g.delta.mean():+.3f}", f"{pr.std(ddof=1):.3f}", " / ".join(f"{v:+.3f}" for v in pr),
                     f"{g[g.called].delta.mean():+.3f} (n={g.called.sum()})", (f"{g[~g.called].delta.mean():+.3f} (n={(~g.called).sum()})" if (~g.called).any() else "— (n=0)")])
    add(md_table(["question", "mean Δ", "SD (rounds)", "round 1 / 2 / 3", "called a tool", "no call"], rows))
    qd = x.groupby("question_id").delta.mean()
    add(f"\nPositive {int((qd > 0.005).sum())}, negative {int((qd < -0.005).sum())}, near zero {int((qd.abs() <= 0.005).sum())}; "
        f"range {qd.max():+.3f} to {qd.min():+.3f}. Over rounds × models: called {int(x.called.sum())}/{len(x)}.")

    # --- 9. run-to-run variation
    add("\n## 9. Run-to-run variation (T1 + T2: same parsed answer in all three rounds; per task SD over rounds of the model mean)\n")
    s = d[d.task != "F"]
    rows = []
    for c in CONDS:
        g = s[s.condition == c].groupby(["model", "question_id"])
        same = g.answer.nunique() == 1
        sc_same = g.score.nunique() == 1
        sd_task = (tm.xs(c, level="condition").groupby(["model", "task"]).std(ddof=1)).groupby("task").mean()
        rows.append([c, f"{same.mean() * 100:.1f}%", f"{sc_same.mean() * 100:.1f}%",
                     f"{sd_task.mean():.3f}", ", ".join(f"{LABEL[t]} {v:.3f}" for t, v in sd_task.items())])
    add(md_table(["condition", "same answer, 3 rounds", "same score, 3 rounds", "mean SD of model×task score", "by task"], rows))
    fx = d[d.task == "F"].pivot_table(index=["model", "condition", "question_id"], columns="round", values="score")
    add("\nT3 judge-mean score correlation between rounds (same model, condition, question): "
        + ", ".join(f"r{a}-r{b} r = {fx[a].corr(fx[b]):.3f}" for a, b in ((1, 2), (2, 3), (1, 3))))

    # --- 10. tokens and cost
    add("\n## 10. Tokens and list-price cost per question (mean over rounds and models)\n")
    rows = []
    d = d[(d.in_tok + d.out_tok) > 0]   # 15 April rows have no token record
    add(f"(rows without a token record excluded: {int(((df.in_tok + df.out_tok) == 0).sum())})")
    g = d.groupby("condition")[["in_tok", "out_tok", "cost"]].mean()
    for c in CONDS:
        rows.append([c, f"{g.loc[c, 'in_tok']:.0f}", f"{g.loc[c, 'out_tok']:.0f}", f"{g.loc[c, 'in_tok'] + g.loc[c, 'out_tok']:.0f}",
                     f"{g.loc[c, 'cost'] * 1000:.3f}"])
    add(md_table(["condition", "input tokens", "output tokens", "total", "cost per 1,000 questions ($)"], rows))
    per_model = d.groupby(["model", "condition"])[["in_tok", "out_tok", "cost"]].mean()
    tok = (per_model.in_tok + per_model.out_tok).unstack()
    cst = per_model.cost.unstack()
    for c in ["tool", "tool_resolved", "graph_in_context"]:
        add(f"- {c} / no_tool, mean over models: tokens × {(tok[c] / tok['no_tool']).mean():.1f}, cost × {(cst[c] / cst['no_tool']).mean():.1f}; "
            f"models where cost is lower than no_tool: {[SHORT[m] for m in cst.index if cst.loc[m, c] < cst.loc[m, 'no_tool']]}")
    add("\nCost per question by model and condition ($ per 1,000 questions):\n")
    add(md_table(["model", *CONDS], [[SHORT[m]] + [f"{cst.loc[m, c] * 1000:.2f}" for c in CONDS] for m in models]))
    return "\n".join(L)


def judge_report(df):
    L = []
    add = L.append
    # unique judged answers: the round-1 tool_resolved copies of April tool answers would count twice
    f = df[(df.task == "F") & (df.origin != "april_copy")].copy()
    f["judged"] = f.judged.fillna(False).astype(bool)
    jc = ["j_anthropic", "j_google", "j_openai"]
    add("## J. T3 judges (all judged answers: 3 rounds × 5 conditions minus prompt_only, plus the April answers)\n")
    add(f"Answers in the analysis: {len(f)}; judged by all three: {int(f.judged.sum())}; not judged (empty or no answer, scored 0): {int((~f.judged).sum())}\n")
    j = f.dropna(subset=jc)
    from sklearn.metrics import cohen_kappa_score
    import krippendorff
    rows = [[c[2:], f"{j[c].mean():.2f}", f"{j[c].std(ddof=1):.2f}"] for c in jc]
    add(md_table(["judge (company)", "mean", "s.d."], rows))
    rows = []
    for a, b in (("j_anthropic", "j_google"), ("j_anthropic", "j_openai"), ("j_google", "j_openai")):
        rows.append([f"{a[2:]} vs {b[2:]}", f"{cohen_kappa_score(j[a].astype(int), j[b].astype(int), weights='quadratic'):.3f}",
                     f"{j[a].corr(j[b]):.3f}", f"{((j[a] - j[b]).abs() <= 1).mean() * 100:.1f}%"])
    add("\n" + md_table(["pair", "Cohen's κ (quadratic)", "Pearson r", "within 1 point"], rows))
    R = j[jc].values.astype(float)
    spread = R.max(1) - R.min(1)
    add(f"\nKrippendorff's α (interval): {krippendorff.alpha(reliability_data=R.T, level_of_measurement='interval'):.3f}; "
        f"α (ordinal): {krippendorff.alpha(reliability_data=R.T, level_of_measurement='ordinal'):.3f}")
    add(f"All three identical {(spread == 0).mean() * 100:.1f}%, max−min = 1: {(spread == 1).mean() * 100:.1f}%, = 2: "
        f"{(spread == 2).mean() * 100:.1f}%, ≥ 3: {(spread >= 3).mean() * 100:.1f}%; within 1 point (all three) {(spread <= 1).mean() * 100:.1f}%")
    # own-company preference: judge minus mean of the other two, own-company answers vs other answers
    add("\nOwn-company preference (judge score − mean of the other two judges; 0–5 scale):\n")
    rows = []
    jm = j.copy()
    jm["company"] = jm.model.map(company)
    for c in jc:
        others = [o for o in jc if o != c]
        diff = jm[c] - jm[others].mean(1)
        own = jm.company == c[2:]
        if own.sum() == 0:
            continue
        t = stats.mannwhitneyu(diff[own], diff[~own], alternative="two-sided")
        rows.append([c[2:], f"{diff[own].mean():+.3f} (n={own.sum()})", f"{diff[~own].mean():+.3f} (n={(~own).sum()})",
                     f"{diff[own].mean() - diff[~own].mean():+.3f}", f"{t.pvalue:.4f}"])
    add(md_table(["judge", "on own-company models", "on other models", "difference", "Mann-Whitney p"], rows))
    add("\nT3 score per model, three-judge mean vs without the own-company judge (0–1, mean over rounds and conditions no_tool/tool):\n")
    sub = f[f.condition.isin(["no_tool", "tool"])]
    g = sub.groupby(["model", "condition"])[["score", "score_loo"]].mean().unstack()
    rows = []
    for m in MODELS:
        if m not in g.index:
            continue
        dl = g.loc[m, ("score", "tool")] - g.loc[m, ("score", "no_tool")]
        dll = g.loc[m, ("score_loo", "tool")] - g.loc[m, ("score_loo", "no_tool")]
        rows.append([SHORT[m], f"{g.loc[m, ('score', 'no_tool')]:.3f}", f"{g.loc[m, ('score_loo', 'no_tool')]:.3f}",
                     f"{dl:+.3f}", f"{dll:+.3f}"])
    add(md_table(["model", "no_tool (3 judges)", "no_tool (LOO)", "Δ (3 judges)", "Δ (LOO)"], rows))
    return "\n".join(L)


def april_panel_check(df):
    """New panel vs April panel on the April answers (9 models x 2 conditions x 15)."""
    old = pd.read_csv(ROOT / "results_revision/judge_scores_t3_original.csv")
    f = df[(df.task == "F") & (df.origin == "april") & (df.condition.isin(["no_tool", "tool"]))]
    f = f.assign(short=f.model.map(SHORT))
    mg = f.merge(old, left_on=["short", "condition", "question_id"], right_on=["model", "condition", "question_id"])
    r = mg.score.corr(mg.mean_score_normalized)
    dl_new = mg.pivot_table(index="short", columns="condition", values="score")
    dl_old = mg.pivot_table(index="short", columns="condition", values="mean_score_normalized")
    return (f"## K. New judge panel vs April panel on the April T3 answers (n = {len(mg)}; Nemotron's April tool answers are not in the analysis, its round 1 is the fresh run)\n\n"
            f"Pearson r = {r:.3f}; mean (0–5) April {mg.mean_score_normalized.mean() * 5:.2f}, new {mg.score.mean() * 5:.2f}. "
            f"Per-model T3 Δ (tool − no_tool) correlation between panels: "
            f"{(dl_new.tool - dl_new.no_tool).corr(dl_old.tool - dl_old.no_tool):.3f}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "evaluations.pkl"
    if args.rebuild or not cache.exists():
        df = assemble()
        df.to_pickle(cache)
        df.drop(columns=[]).to_csv(OUT / "evaluations.csv", index=False)
    df = pd.read_pickle(cache)
    n, bad, missing_cells = check_counts(df)
    head = [f"# Follow-up run analysis\n",
            f"Evaluations: {len(df)}; cells (round × model × condition): {len(n)}, missing {missing_cells}, wrong size {len(bad)} {bad[:5]}",
            f"Origins: {dict(Counter(df.origin))}",
            f"Status: {dict(Counter(df.status))}; API errors left: {int(df.api_error.sum())}",
            "Parse errors by condition and round: " + str(df[df.status == "parse_error"].groupby(["condition", "round"]).size().to_dict()),
            ""]
    body = [report(df, list(MODELS), "11models"),
            "\n\n# Sensitivity: the 9 models common to April\n", report(df, list(APRIL_MODELS), "9models"),
            "\n\n", judge_report(df), "\n\n", april_panel_check(df)]
    (OUT / "report.md").write_text("\n".join(head) + "\n" + "\n".join(body) + "\n")
    print(f"wrote {OUT / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
