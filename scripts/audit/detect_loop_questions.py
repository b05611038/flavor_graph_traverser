#!/usr/bin/env python3
"""
Detect questions where validate_descriptors was called with the same
arguments 3+ times — indicating a retry loop that completed but may
have wasted tokens or produced an unreliable answer.

Usage:
    python scripts/audit/detect_loop_questions.py
    python scripts/audit/detect_loop_questions.py --run results/merge_all
    python scripts/audit/detect_loop_questions.py --threshold 3 --output loops.json
"""

import argparse
import glob
import json
import os
import sys
from pathlib import Path


def find_cache_files(run_dir: str) -> list[str]:
    patterns = [
        f"{run_dir}/*/cache/**/*.json",
        f"{run_dir}/*/*/cache/**/*.json",
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))
    return files


def analyze_cache_file(path: str, threshold: int) -> dict | None:
    """
    Return a report dict if this question has any validate_descriptors
    argument set repeated >= threshold times, else None.
    """
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception as e:
        print(f"  ⚠ Could not read {path}: {e}", file=sys.stderr)
        return None

    history = d.get("conversation_history", [])
    if not history:
        return None

    # Count validate_descriptors calls by canonical arg key
    call_counts: dict[tuple, int] = {}
    for msg in history:
        # Native tool path: tool_calls in assistant message
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            if fn.get("name") == "validate_descriptors":
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                    key = tuple(sorted(args.get("descriptors", [])))
                    call_counts[key] = call_counts.get(key, 0) + 1
                except Exception:
                    pass

        # ICL path: tool call embedded in assistant content text
        content = msg.get("content", "") or ""
        if msg.get("role") == "assistant" and "validate_descriptors" in content:
            # Parse TOOL_CALL: {"name": "validate_descriptors", "args": {...}}
            import re
            for m in re.finditer(
                r'TOOL_CALL:\s*\{[^}]*"name"\s*:\s*"validate_descriptors"[^}]*"args"\s*:\s*(\{[^}]+\})',
                content,
            ):
                try:
                    args = json.loads(m.group(1))
                    key = tuple(sorted(args.get("descriptors", [])))
                    call_counts[key] = call_counts.get(key, 0) + 1
                except Exception:
                    pass

    if not call_counts:
        return None

    max_repeat = max(call_counts.values())
    if max_repeat < threshold:
        return None

    # Find the worst offenders
    repeated = {
        str(list(k)): v for k, v in call_counts.items() if v >= threshold
    }

    metrics = d.get("metrics", {})
    return {
        "question_id": d.get("question_id"),
        "model": d.get("model"),
        "condition": d.get("condition"),
        "task_type": d.get("task_type"),
        "model_answer": d.get("model_answer"),
        "is_correct": d.get("is_correct"),
        "max_repeat": max_repeat,
        "repeated_calls": repeated,
        "total_tokens": metrics.get("total_tokens", 0),
        "validation_calls": metrics.get("validation_calls", 0),
        "reasoning_calls": metrics.get("reasoning_calls", 0),
        "cache_path": path,
    }


def main():
    parser = argparse.ArgumentParser(description="Detect retry-loop questions in cached results")
    parser.add_argument("--run", default="results/merge_all",
                        help="Run directory to scan (default: results/merge_all)")
    parser.add_argument("--threshold", type=int, default=3,
                        help="Min repeat count to flag (default: 3)")
    parser.add_argument("--output", default=None,
                        help="Save flagged questions to this JSON file")
    args = parser.parse_args()

    print(f"Scanning: {args.run}")
    print(f"Threshold: same descriptors called >= {args.threshold}x\n")

    files = find_cache_files(args.run)
    print(f"Found {len(files)} cache files\n")

    flagged = []
    for path in files:
        result = analyze_cache_file(path, args.threshold)
        if result:
            flagged.append(result)

    if not flagged:
        print("✓ No retry loops detected.")
        return

    # Sort by max_repeat descending
    flagged.sort(key=lambda x: (-x["max_repeat"], -x["total_tokens"]))

    print(f"⚠ Found {len(flagged)} questions with retry loops:\n")
    print(f"{'Model':<35} {'Cond':<8} {'QID':<45} {'Repeat':<8} {'Tokens':<10} {'Ans':<6} {'Correct'}")
    print("-" * 130)
    for r in flagged:
        model = r["model"].split("/")[-1] if r["model"] else ""
        print(
            f"{model:<35} {r['condition']:<8} {r['question_id']:<45} "
            f"{r['max_repeat']:<8} {r['total_tokens']:<10} {str(r['model_answer']):<6} {r['is_correct']}"
        )
        for descriptors, count in r["repeated_calls"].items():
            print(f"    → {count}x {descriptors}")

    print(f"\nTotal flagged: {len(flagged)}")

    # Summary by model
    from collections import Counter
    by_model = Counter(r["model"].split("/")[-1] for r in flagged)
    print("\nBy model:")
    for model, count in by_model.most_common():
        print(f"  {model}: {count}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump({"threshold": args.threshold, "flagged": flagged}, f, indent=2)
        print(f"\nSaved to {args.output}")

    # Print cache paths for easy deletion / re-run
    print("\nCache files to delete for re-run:")
    for r in flagged:
        print(f"  {r['cache_path']}")


if __name__ == "__main__":
    main()
