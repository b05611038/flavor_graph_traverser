#!/usr/bin/env python3
"""
Rebuild results.json for each model and merged_results.json from cache files.

Use this after running judge passes to incorporate judge scores into the
results files that the auditor site reads. Reads all cache files directly —
no API calls, no re-evaluation.

Multi-judge support: reads judge_scores dict from cache, computes mean score
across all judges that have run, and writes judge_score (mean 0-5) for
compatibility with the auditor site and batch_runner summary format.

Usage:
    python scripts/rebuild_results.py
    python scripts/rebuild_results.py --run results/merge_all
    python scripts/rebuild_results.py --run results/merge_all --dry-run
"""

import argparse
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path


def write_atomic(path: Path, data: dict):
    """Write JSON atomically via tmp file + rename."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def mean_judge_score(judge_scores: dict) -> float | None:
    """Return mean of valid (non-None) judge scores (0-5 scale), or None if no scores."""
    valid = [v for v in judge_scores.values() if v is not None]
    return sum(valid) / len(valid) if valid else None


def load_cache_file(path: Path) -> dict | None:
    """Load a cache file, return None on error."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def compute_score(data: dict) -> float:
    """
    Compute the canonical 0-1 score for a cache entry.

    - F-category: mean judge score / 5
    - Others: 1.0 if is_correct else 0.0 (or use existing score field)
    """
    judge_scores = data.get("judge_scores", {})
    if judge_scores:
        mean = mean_judge_score(judge_scores)
        if mean is not None:
            return mean / 5.0

    # Fall back to existing score or is_correct
    if "score" in data and data["score"] is not None:
        return float(data["score"])
    return 1.0 if data.get("is_correct") else 0.0


def calc_accuracy(entries):
    if not entries:
        return 0.0
    return sum(1 for e in entries if e.get("is_correct")) / len(entries)


def calc_avg_score(entries):
    if not entries:
        return 0.0
    return sum(e["_score"] for e in entries) / len(entries)


def calc_macro_score(by_task):
    if not by_task:
        return 0.0
    cat_scores = [calc_avg_score(res) for res in by_task.values()]
    return sum(cat_scores) / len(cat_scores)


def calc_avg_judge_score(entries):
    scored = [e["_judge_score"] for e in entries if e.get("_judge_score") is not None]
    return sum(scored) / len(scored) if scored else None


def build_results_for_model(model_dir: Path, dry_run: bool = False) -> dict | None:
    """
    Read all cache files under model_dir/cache, build and write results.json.
    Returns the results dict, or None if no cache files found.
    """
    cache_root = model_dir / "cache"
    if not cache_root.exists():
        return None

    entries = []
    for qfile in sorted(cache_root.rglob("*.json")):
        # Skip tmp files
        if qfile.suffix == ".tmp":
            continue
        # Cache layout: <cache_root>/<provider>/<model>/<condition>/<qid>.json
        rel = qfile.relative_to(cache_root)
        parts = rel.parts
        if len(parts) < 3:
            continue

        data = load_cache_file(qfile)
        if data is None:
            continue

        # Compute judge_score from multi-judge dict
        judge_scores = data.get("judge_scores", {})
        judge_score_mean = mean_judge_score(judge_scores)

        # Compute canonical score
        score = compute_score(data)

        entry = dict(data)
        entry["score"] = score
        # Write mean judge score (0-5) for auditor site compatibility
        if judge_score_mean is not None:
            entry["judge_score"] = judge_score_mean
        # Internal fields for summary computation
        entry["_score"] = score
        entry["_judge_score"] = judge_score_mean

        entries.append(entry)

    if not entries:
        return None

    # Group for summary
    by_mc = defaultdict(list)
    by_model = defaultdict(list)
    by_condition = defaultdict(list)
    by_task = defaultdict(list)

    for e in entries:
        model = e.get("model", "unknown")
        condition = e.get("condition", "unknown")
        task_type = e.get("task_type", "")
        by_mc[(model, condition)].append(e)
        by_model[model].append(e)
        by_condition[condition].append(e)
        if task_type:
            by_task[task_type].append(e)

    summary = {
        "total_evaluations": len(entries),
        "elapsed_seconds": 0,
        "by_model_condition": {},
        "by_model": {},
        "by_condition": {},
        "by_task_type": {},
        "overall_accuracy": calc_accuracy(entries),
        "overall_score": calc_avg_score(entries),
        "macro_score": calc_macro_score(by_task),
    }

    f_entries = [e for e in entries if e.get("_judge_score") is not None]
    if f_entries:
        summary["f_category_avg_score"] = calc_avg_judge_score(f_entries)
        summary["f_category_count"] = len(f_entries)

    for (model, condition), res_list in by_mc.items():
        mc_by_task = defaultdict(list)
        for r in res_list:
            if r.get("task_type"):
                mc_by_task[r["task_type"]].append(r)
        entry = {
            "count": len(res_list),
            "accuracy": calc_accuracy(res_list),
            "avg_score": calc_avg_score(res_list),
            "macro_score": calc_macro_score(mc_by_task),
            "avg_tokens": (
                sum(r.get("metrics", {}).get("total_tokens", 0) for r in res_list) / len(res_list)
            ),
            "avg_latency_ms": (
                sum(r.get("metrics", {}).get("latency_ms", 0) for r in res_list) / len(res_list)
            ),
        }
        avg_judge = calc_avg_judge_score(res_list)
        if avg_judge is not None:
            entry["f_avg_judge_score"] = avg_judge
        summary["by_model_condition"][f"{model}_{condition}"] = entry

    for model, res_list in by_model.items():
        m_by_task = defaultdict(list)
        for r in res_list:
            if r.get("task_type"):
                m_by_task[r["task_type"]].append(r)
        entry = {
            "count": len(res_list),
            "accuracy": calc_accuracy(res_list),
            "avg_score": calc_avg_score(res_list),
            "macro_score": calc_macro_score(m_by_task),
        }
        avg_judge = calc_avg_judge_score(res_list)
        if avg_judge is not None:
            entry["f_avg_judge_score"] = avg_judge
        summary["by_model"][model] = entry

    for condition, res_list in by_condition.items():
        c_by_task = defaultdict(list)
        for r in res_list:
            if r.get("task_type"):
                c_by_task[r["task_type"]].append(r)
        entry = {
            "count": len(res_list),
            "accuracy": calc_accuracy(res_list),
            "avg_score": calc_avg_score(res_list),
            "macro_score": calc_macro_score(c_by_task),
        }
        avg_judge = calc_avg_judge_score(res_list)
        if avg_judge is not None:
            entry["f_avg_judge_score"] = avg_judge
        summary["by_condition"][condition] = entry

    for task_type, res_list in sorted(by_task.items()):
        entry = {
            "count": len(res_list),
            "accuracy": calc_accuracy(res_list),
            "avg_score": calc_avg_score(res_list),
        }
        avg_judge = calc_avg_judge_score(res_list)
        if avg_judge is not None:
            entry["avg_judge_score"] = avg_judge
        summary["by_task_type"][task_type] = entry

    # Load existing metadata if present
    existing_results_file = model_dir / "results.json"
    metadata = {}
    if existing_results_file.exists():
        try:
            existing = json.loads(existing_results_file.read_text())
            metadata = existing.get("metadata", {})
        except Exception:
            pass

    # Strip internal fields from output entries
    output_entries = []
    for e in entries:
        out = {k: v for k, v in e.items() if not k.startswith("_")}
        output_entries.append(out)

    results_doc = {
        "run_status": "complete",
        "metadata": metadata,
        "summary": summary,
        "results": output_entries,
    }

    if not dry_run:
        write_atomic(model_dir / "results.json", results_doc)

    return results_doc


def rebuild_merged(run_dir: Path, dry_run: bool = False):
    """Merge all results.json files under run_dir into merged_results.json."""
    all_results = []
    results_files = sorted(run_dir.glob("*/results.json"))

    for rf in results_files:
        try:
            d = json.loads(rf.read_text())
            all_results.extend(d.get("results", []))
        except Exception as e:
            print(f"  Warning: could not read {rf}: {e}")

    merged = {
        "run_status": "merged",
        "summary": {
            "total_evaluations": len(all_results),
            "source": f"auto-merged from {len(results_files)} results files",
        },
        "results": all_results,
    }

    merged_path = Path("results/merged_results.json")
    if not dry_run:
        write_atomic(merged_path, merged)

    return len(all_results), len(results_files)


def run_once(run_dir: Path, dry_run: bool = False, quiet: bool = False) -> None:
    model_dirs = sorted(d for d in run_dir.iterdir() if d.is_dir() and d.name != "logs")
    for model_dir in model_dirs:
        result = build_results_for_model(model_dir, dry_run=dry_run)
        if result is None:
            if not quiet:
                print(f"  {model_dir.name}: no cache files, skipped")
            continue
        if not quiet:
            n = result["summary"]["total_evaluations"]
            acc = result["summary"]["overall_accuracy"]
            macro = result["summary"]["macro_score"]
            f_avg = result["summary"].get("f_category_avg_score")
            f_str = f" | F judge avg: {f_avg:.2f}/5" if f_avg is not None else " | F: not judged"
            action = "[dry-run]" if dry_run else "✓"
            print(f"  {action} {model_dir.name}: {n} evals | acc={acc:.1%} | macro={macro:.1%}{f_str}")

    n_total, n_files = rebuild_merged(run_dir, dry_run=dry_run)
    if not quiet:
        action = "[dry-run]" if dry_run else "✓"
        print(f"  {action} merged_results.json: {n_total} total evals from {n_files} files")


def main():
    parser = argparse.ArgumentParser(description="Rebuild results.json from cache files")
    parser.add_argument("--run", default="results/merge_all",
                        help="Run directory to rebuild")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing files")
    parser.add_argument("--watch", type=int, metavar="SECONDS", nargs="?", const=30,
                        help="Watch mode: rebuild every N seconds (default 30). "
                             "Site picks up changes automatically via mtime detection.")
    args = parser.parse_args()

    run_dir = Path(args.run)
    if not run_dir.exists():
        print(f"Error: {run_dir} does not exist")
        return

    print(f"Run dir: {run_dir}")
    if args.watch:
        print(f"Watch mode: rebuilding every {args.watch}s (Ctrl+C to stop)")
    print(f"Dry run: {args.dry_run}")
    print()

    if args.watch:
        import time
        iteration = 0
        while True:
            iteration += 1
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] Rebuild #{iteration}")
            run_once(run_dir, dry_run=args.dry_run, quiet=False)
            print()
            time.sleep(args.watch)
    else:
        run_once(run_dir, dry_run=args.dry_run, quiet=False)


if __name__ == "__main__":
    main()
