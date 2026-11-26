#!/usr/bin/env python3
"""
Check that every F-category result in a run has a score from every panel judge.

For runs judged inside the evaluation cache (the original pipeline, scripts/experiment/run_all.sh): F answers
are scored as the mean of three judges, and a record missing one judge (or holding None after a judge failure)
would silently get a mean over fewer judges. The follow-up runs are judged separately by run_judges.py into
results_revision/judging/; judge_scores.py reports how many answers have all three judges.

Usage:
    python scripts/revision/check_judge_coverage.py --run results_revision/run_YYYYMMDD_HHMMSS
Exit code 1 if any record is incomplete.
"""

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

PANEL = ("anthropic/claude-opus-4.6", "google/gemini-3.1-pro-preview", "openai/gpt-5.4-pro")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="run directory containing <model>/cache/...")
    ap.add_argument("--judges", nargs="+", default=list(PANEL))
    args = ap.parse_args()

    files = sorted({Path(p) for pat in (f"{args.run}/*/cache/**/F_*.json", f"{args.run}/*/*/cache/**/F_*.json")
                    for p in glob.glob(pat, recursive=True)})
    if not files:
        print(f"No F-category cache files under {args.run} — nothing to check.")
        return 0

    problems = Counter()
    bad = []
    for f in files:
        data = json.loads(f.read_text())
        scores = data.get("judge_scores") or {}
        missing = [j for j in args.judges if j not in scores]
        failed = [j for j in args.judges if j in scores and scores[j] is None]
        if not (data.get("model_response_text") or "").strip():
            problems["no_response"] += 1
            bad.append((f, "no model response"))
        elif missing or failed:
            problems["incomplete"] += 1
            bad.append((f, f"missing={missing} failed={failed}"))

    print(f"F records: {len(files)}; complete: {len(files) - len(bad)}; problems: {dict(problems)}")
    for f, why in bad[:50]:
        print(f"  {'/'.join(f.parts[-4:])}: {why}")
    if len(bad) > 50:
        print(f"  ... and {len(bad) - 50} more")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
