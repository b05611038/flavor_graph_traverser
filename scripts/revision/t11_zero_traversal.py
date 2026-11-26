"""T1.1 under the tool-augmented condition: evaluations without any traversal call (get_parent/get_children).

Counts, over the three rounds and 11 models:
  - zero-traversal evaluations, and how many had validate_descriptors return the question's descriptor as invalid;
  - how many of those then answered NONE, and how many of those NONE answers are correct;
  - how many NONE answers that give a reason cite the descriptor's absence from the graph or the lack of confirmed evidence;
  - the paired comparison: same model and question, runs with vs without a traversal call (mean score, NONE rate, Wilcoxon).

Usage: python scripts/revision/t11_zero_traversal.py   (reads the same transcripts as analyze_revision.py)
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("ar", ROOT / "scripts/revision/analyze_revision.py")
ar = importlib.util.module_from_spec(spec)
sys.argv = sys.argv[:1]
exec(compile(open(spec.origin).read().split("if __name__")[0], spec.origin, "exec"), ar.__dict__)

ABSENCE = re.compile(
    r"not (?:a )?(?:valid|confirmed|present|found|in|listed|available|recognized|recognised)|(?:does|did)(?:n't| not) (?:exist|appear)"
    r"|invalid|no (?:confirmed |graph |positive |direct )?(?:evidence|entry|match|results?)|cannot (?:confirm|verify|be (?:traced|confirmed|verified))"
    r"|can(?:'|’)t (?:confirm|verify)|absent|unable to (?:confirm|verify|find)", re.I)


def tool_text(r):
    """Tool results: native tool messages, or TOOL_RESULT lines for in-context tool use."""
    return " ".join(m["content"] for m in r["conversation_history"]
                    if m.get("role") == "tool" or (m.get("role") == "user" and "TOOL_RESULT" in (m.get("content") or "")))


def descriptor_invalid(r, desc):
    for m in re.finditer(r'\{[^{}]*"invalid"[^{}]*\}', tool_text(r)):
        try:
            j = json.loads(m.group(0))
        except ValueError:
            continue
        if desc in j.get("invalid", []):
            return True
    return False


rows = []
for n, r, _, origin in ar.gather():
    if r["condition"] not in ("tool", "tool_rerun") or "root_classification" not in r["question_id"]:
        continue
    desc = re.search(r"that '(.+?)' belongs", r["question_text"]).group(1)
    ans = r.get("model_answer")
    body = " ".join((m.get("thinking_content") or "") + " " + (m.get("content") or "")
                    for m in r["conversation_history"] if m["role"] == "assistant")
    body = re.sub(r"Therefore, I select \(NONE\)", "", body).strip()
    rows.append(dict(round=n, model=r["model"], question=r["question_id"],                      traversal=(r.get("metrics") or {}).get("reasoning_calls") or 0,
                     invalid=descriptor_invalid(r, desc), score=0.0, none=False,
                     gold_none=r["correct_answer"] == [], reason=len(body) >= 20, cites_absence=bool(ABSENCE.search(body))))
d = pd.DataFrame(rows).drop(columns=["score", "none"])
# scores and NONE flags as used in the manuscript (fixed parser), from the assembled evaluations
ev = pd.read_pickle(ROOT / "results_revision/analysis/evaluations.pkl")
ev = ev[(ev.condition == "tool") & (ev.task == "A1")][["round", "model", "question_id", "score", "none_sel", "traversal_calls"]]
d = d.merge(ev.rename(columns={"question_id": "question", "none_sel": "none"}), on=["round", "model", "question"], how="inner", validate="1:1")
assert len(d) == 1650 and (d.traversal == d.traversal_calls).all(), len(d)
d["none"] = d["none"].astype(bool)

z = d[d.traversal == 0]
zi = z[z.invalid]
zn = zi[zi.none]
print(f"T1.1 tool-augmented evaluations: {len(d)}; without a traversal call: {len(z)} ({len(z) / len(d):.1%})")
print(f"  validate_descriptors returned the descriptor as invalid: {len(zi)} ({len(zi) / len(z):.1%})")
print(f"  of these, answered NONE: {len(zn)} ({len(zn) / len(zi):.1%}); NONE correct: {int(zn.gold_none.sum())} ({zn.gold_none.mean():.1%})")
zr = zn[zn.reason]
print(f"  NONE answers giving a reason: {len(zr)}; citing absence or lack of confirmed evidence: {int(zr.cites_absence.sum())} ({zr.cites_absence.mean():.1%})")
print(f"  mean score: no traversal {z.score.mean():.3f}; with traversal {d[d.traversal > 0].score.mean():.3f}")
print(f"  NONE rate: no traversal {z.none.mean():.1%}; with traversal {d[d.traversal > 0].none.mean():.1%}")

p = d.assign(stopped=d.traversal == 0).groupby(["model", "question", "stopped"]).agg(score=("score", "mean"), none=("none", "mean")).unstack("stopped").dropna()
diff = p[("score", False)] - p[("score", True)]
w = stats.wilcoxon(diff)
print(f"Paired (same model and question, runs with and without a traversal call): {len(p)} pairs, "
      f"{p.index.get_level_values(0).nunique()} models; score {p[('score', True)].mean():.3f} vs {p[('score', False)].mean():.3f} "
      f"(difference {diff.mean():+.3f}, Wilcoxon P={w.pvalue:.2g}); NONE {p[('none', True)].mean():.1%} vs {p[('none', False)].mean():.1%}")
