#!/usr/bin/env python3
"""
Read the follow-up judge panel's T3 scores (written by scripts/revision/run_judges.py).

    from judge_scores import load_scores
    table = load_scores()          # {(source, model, condition, question_id): row}

Each row:
    judges      {judge_id: score 0-5}, final "success" records only
    mean        mean of the available judges, 0-5          (main score)
    score       mean / 5, the 0-1 task score                (as compute_question_score)
    loo_mean    mean without the judge from the evaluated model's own company (leave-own-company-out);
                equals `mean` for models whose company has no judge on the panel
    complete    True if all panel judges scored it

A record counts only if it is final for the answer it scored; answers are matched by
source/model/condition/question_id (the runner guarantees the answer hash).

Usage (checks + summary):
    python scripts/revision/judge_scores.py [--sources run1 run1_nemotron_tool april]
"""

import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = ROOT / "results_revision/judging"


def company(model_id):
    """Company of an evaluated model or judge id: the OpenRouter prefix (e.g. 'openai')."""
    return model_id.split("/")[0]


def load_scores(out=DEFAULT_OUT, slot="main", panel=None):
    import yaml
    panel = panel or [j["id"] for j in yaml.safe_load(open(ROOT / "configs/models.yaml"))["revision_judges"]]
    raw = defaultdict(dict)
    for f in glob.glob(str(Path(out) / "*" / slot / "**/*.json"), recursive=True):
        r = json.loads(Path(f).read_text())
        if r.get("status") != "success" or r["judge_model"] not in panel:
            continue
        key = (r["source"], r["model"], r["condition"], r["question_id"])
        if r["judge_model"] in raw[key]:
            raise ValueError(f"two records for {key} by {r['judge_model']}")
        raw[key][r["judge_model"]] = r["score"]
    table = {}
    for key, js in raw.items():
        own = company(key[1])
        others = [s for j, s in js.items() if company(j) != own]
        m = mean(js.values())
        table[key] = {"judges": js, "mean": m, "score": m / 5.0,
                      "loo_mean": mean(others) if others else None,
                      "complete": set(js) == set(panel)}
    return table


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", nargs="*")
    args = ap.parse_args()
    t = load_scores()
    if args.sources:
        t = {k: v for k, v in t.items() if k[0] in args.sources}
    print(f"{len(t)} answers; complete (all judges): {sum(v['complete'] for v in t.values())}")
    by_src = defaultdict(list)
    for k, v in t.items():
        by_src[k[0]].append(v["mean"])
    for s, xs in sorted(by_src.items()):
        print(f"  {s:20} n={len(xs):4}  mean {mean(xs):.2f}/5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
