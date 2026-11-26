#!/usr/bin/env python3
"""
Select tool-condition evaluations to re-run under label resolution (condition `tool_resolved`).

An evaluation is AFFECTED if at least one tool call it made returns a different
result under label resolution (condition `tool_resolved`) than under exact matching
(condition `tool`). Every executed call is replayed through both executors, so the
selection follows exactly what LabelResolver changes — nothing is hand-listed.
Each affected evaluation is labelled with the kind(s) of fix that changed it:

  layer_label             bare "floral" / "green/vegetative"
  layer_label_variant     "green vegetative", "green/vegetal", "green/ vegetative"
  benchmark_spelling      "green/vegetable" (system-graph root name), "whisky" (tool graph: "whiskey")
  tool_graph_misspelling  "grapefruit" / "maple syrup" queries (file has "graphfruit" / "mapple syrup")
  display_correction      output changed only because a misspelled / underscored node
                          is now shown corrected (e.g. get_children("citrus fruit"))
  word_form               related forms of wheel terms ("fruit" -> "fruity", "spice" -> "spices",
                          "raisins" -> "raisin"); reviewed list + singular/plural rule
  query_spelling_variant  same-word spelling variants models typed ("smokey", "winy", "animallic")
  surface_normalization   case and separators: space / "_" / "-" / "/" treated alike or missing
                          ("black tea", "blacktea", "musty earthy", "Floral"), ring written
                          without parentheses ("floral middle layer")

Output rows (pairs CSV for run_experiment.py --pairs), column `purpose`:
  label_fix        affected evaluation under `tool_resolved`
  paired_control   (--paired) same affected evaluation under `tool_rerun`, so the
                   label effect is estimated within one session, free of drift
  noise_control    unaffected evaluation under `tool_rerun` (stratified by task in
                   proportion to the affected set), to estimate run-to-run variation

Unaffected transcripts never touched a changed lookup, so their tool_resolved
outcome equals the original tool outcome if generation is deterministic; the
noise-control rows measure how far that holds.

Call extraction:
  native tools — every tool_call in an assistant turn;
  ICL tools    — the first TOOL_CALL line of an assistant turn answered with a
                 TOOL_RESULT message (what the evaluator actually executed).
Calls refused by the budget / repeat guard are still replayed, so the selection is
conservative (may over-include, never under-include).

Usage:
    python scripts/revision/select_rerun_pairs.py \
        --out results_revision/rerun_pairs.csv \
        --detail results_revision/rerun_detail.csv \
        --flagged results_revision/flagged_by_fix.csv \
        --noise-sample 100 [--paired]
"""

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph  # noqa: E402
from FlavorGraphTraverser.evaluation.tools import build_executor  # noqa: E402
from FlavorGraphTraverser.evaluation.utils.icl_tools import parse_icl_tool_call  # noqa: E402

# Models not re-run selectively: grok-4.1-fast and mistral-medium-3.1 were retired by
# their providers and replaced (grok-4.20, mistral-medium-3-5 get full runs);
# gpt-oss-20b was a local test model, not part of the reported 11.
DEFAULT_EXCLUDE = ("x-ai/grok-4.1-fast", "mistralai/mistral-medium-3.1", "openai/gpt-oss-20b")


def executed_calls(record):
    """Yield (tool_name, args) for each tool call the evaluator executed."""
    history = record.get("conversation_history") or []
    for i, msg in enumerate(history):
        if msg.get("role") != "assistant":
            continue
        native = msg.get("tool_calls") or []
        for tc in native:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(args, dict):
                yield fn.get("name"), args
        if not native:
            nxt = history[i + 1] if i + 1 < len(history) else None
            if nxt and nxt.get("role") == "user" and str(nxt.get("content", "")).startswith("TOOL_RESULT:"):
                name, args = parse_icl_tool_call(msg.get("content") or "")
                if name and isinstance(args, dict):
                    yield name, args


def safe_execute(executor, name, args):
    try:
        return executor.execute(name, args)
    except Exception as e:  # malformed args etc. — identical failure in both modes
        return {"exception": type(e).__name__}


def queried_terms(args):
    q = args.get("descriptors", args.get("descriptor"))
    return [t for t in (q if isinstance(q, list) else [q]) if isinstance(t, str)]


def classify_record(record, exact, resolved):
    """Return (n_calls, n_changed_calls, {category: set(terms)})."""
    n_calls = n_changed = 0
    cats = defaultdict(set)
    for name, call_args in executed_calls(record):
        n_calls += 1
        if safe_execute(exact, name, call_args) == safe_execute(resolved, name, call_args):
            continue
        n_changed += 1
        found = False
        for t in queried_terms(call_args):
            c = resolved.resolver.classify(t)
            if c:
                cats[c].add(t)
                found = True
        if not found:
            # The query was an exact node name; only the displayed output changed.
            cats["display_correction"].update(queried_terms(call_args) or [name])
    return n_calls, n_changed, cats


def stratified_sample(pool, target_counts, rng):
    """Sample from pool (list of dicts with 'task') to match target task counts as closely as possible."""
    by_task = defaultdict(list)
    for d in pool:
        by_task[d["task"]].append(d)
    chosen = []
    for task, n in sorted(target_counts.items()):
        cand = by_task.get(task, [])
        chosen.extend(rng.sample(cand, min(n, len(cand))))
    return chosen


def allocate(n_total, weights):
    """Largest-remainder allocation of n_total across keys in proportion to weights."""
    tot = sum(weights.values())
    if tot == 0 or n_total == 0:
        return {k: 0 for k in weights}
    raw = {k: n_total * w / tot for k, w in weights.items()}
    alloc = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - alloc[k], reverse=True)[: n_total - sum(alloc.values())]:
        alloc[k] += 1
    return alloc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default="results_revision/run1/original_run.json",
                    help="ORIGINAL run's merged results (records with condition 'tool')")
    ap.add_argument("--graph", default="data/graphs/coffee_flavor_wheel.json")
    ap.add_argument("--out", required=True, help="pairs CSV for run_experiment.py --pairs")
    ap.add_argument("--detail", help="optional per-evaluation detail CSV")
    ap.add_argument("--flagged", help="optional CSV of affected (model, question) with fix categories")
    ap.add_argument("--noise-sample", type=int, default=100,
                    help="unaffected evaluations to re-run under tool_rerun (stratified by task)")
    ap.add_argument("--paired", action="store_true",
                    help="also list every affected evaluation under tool_rerun (paired contrast)")
    ap.add_argument("--seed", type=int, default=20261119)
    ap.add_argument("--exclude-model", nargs="*", default=None,
                    help=f"models to skip (default: {' '.join(DEFAULT_EXCLUDE)}); pass with no value to skip none")
    args = ap.parse_args()
    exclude = set(DEFAULT_EXCLUDE if args.exclude_model is None else args.exclude_model)

    data = load_graph_data(args.graph)
    graph = CoffeeDescriptionGraph(data["descriptions"], data["connections"], root=data["root"])
    exact = build_executor(graph, {"label_resolution": "exact"})
    resolved = build_executor(graph, {"label_resolution": "resolve"})

    records = json.load(open(args.results))["results"]
    if any((r.get("run_meta") or {}).get("run_tag") for r in records if r.get("condition") == "tool"):
        print("⚠ --results contains re-run records under condition 'tool'; point it at the ORIGINAL run.")
    records = [r for r in records if r["condition"] == "tool" and r["model"] not in exclude]
    if not records:
        print("No tool-condition records found — nothing to select.")
        return 1

    detail = []
    term_counts = Counter()
    for r in sorted(records, key=lambda r: (r["model"], r["question_id"])):
        n_calls, n_changed, cats = classify_record(r, exact, resolved)
        for c, terms in cats.items():
            for t in terms:
                term_counts[(c, t)] += 1
        detail.append({
            "model": r["model"],
            "question_id": r["question_id"],
            "task": r["question_id"].split("_")[0],
            "n_calls": n_calls,
            "n_changed_calls": n_changed,
            "affected": int(n_changed > 0),
            "categories": "|".join(sorted(cats)),
            "changed_terms": "|".join(sorted({t for ts in cats.values() for t in ts})),
        })

    affected = [d for d in detail if d["affected"]]
    unaffected = [d for d in detail if not d["affected"]]
    rng = random.Random(args.seed)
    target = allocate(min(args.noise_sample, len(unaffected)), Counter(d["task"] for d in affected))
    noise = stratified_sample(unaffected, target, rng)

    rows = [{"model": d["model"], "condition": "tool_resolved", "question_id": d["question_id"],
             "purpose": "label_fix"} for d in affected]
    if args.paired:
        rows += [{"model": d["model"], "condition": "tool_rerun", "question_id": d["question_id"],
                  "purpose": "paired_control"} for d in affected]
    rows += [{"model": d["model"], "condition": "tool_rerun", "question_id": d["question_id"],
              "purpose": "noise_control"} for d in noise]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "condition", "question_id", "purpose"])
        w.writeheader()
        w.writerows(rows)
    if args.detail:
        with open(args.detail, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(detail[0]))
            w.writeheader()
            w.writerows(detail)
    if args.flagged:
        with open(args.flagged, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["question_id", "task", "model", "categories", "changed_terms",
                                              "n_changed_calls"])
            w.writeheader()
            for d in sorted(affected, key=lambda d: (d["question_id"], d["model"])):
                w.writerow({k: d[k] for k in w.fieldnames})

    # ── Report ──
    print(f"tool evaluations scanned: {len(detail)} ({len({d['model'] for d in detail})} models; excluded {sorted(exclude)})")
    print(f"affected (≥1 tool result changes): {len(affected)} on {len({d['question_id'] for d in affected})} questions")
    cat_evals = Counter(c for d in affected for c in d["categories"].split("|") if c)
    print("\naffected evaluations by fix category (an evaluation can have several):")
    for c, n in cat_evals.most_common():
        only = sum(1 for d in affected if d["categories"] == c)
        qs = len({d["question_id"] for d in affected if c in d["categories"].split("|")})
        print(f"  {c:24} {n:4} evals on {qs:3} questions ({only} affected by this category only)")
    print("\nchanged terms:")
    for (c, t), n in sorted(term_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {c:24} {t!r}: {n}")
    by_task = defaultdict(lambda: [0, 0])
    for d in detail:
        by_task[d["task"]][0] += 1
        by_task[d["task"]][1] += d["affected"]
    print("\ntask  evals  affected  noise")
    noise_by_task = Counter(d["task"] for d in noise)
    for t in sorted(by_task):
        print(f"{t:4} {by_task[t][0]:6} {by_task[t][1]:9} {noise_by_task.get(t, 0):6}")
    print("\naffected by model:")
    for m, n in sorted(Counter(d["model"] for d in affected).items()):
        print(f"  {m:40} {n}")
    print(f"\nwrote {args.out} ({len(rows)} rows: {Counter(r['purpose'] for r in rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
