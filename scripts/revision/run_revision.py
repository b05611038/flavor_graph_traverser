#!/usr/bin/env python3
"""
Launch one round of the follow-up experiment (three rounds, results under results_revision/).

Each round lives in its own directory results_revision/run<N>/ with one sub-directory per
job (model x condition, slow models split into parts), so rounds never share a cache and
repeats stay separate. Jobs run as parallel processes, judging off (T3 answers are judged
later), with no shared merged file while running.

Round contents (9 April models = OLD; Grok 4.20 and Mistral Medium 3.5 = NEW, which replace
retired models and therefore have no April round 1):
  round 1   OLD: tool_resolved on the affected evaluations (results_revision/rerun_pairs.csv); the rest of
                 round 1 is the April tool transcripts (unchanged tool results)
            NEW: no_tool, tool_rerun, tool_resolved, all 275 questions
            ALL: graph_in_context (275), prompt_only_noaccess (T1 = A1-A5, 180)
  round 2/3 ALL: no_tool, tool_rerun, tool_resolved, graph_in_context (275),
                 prompt_only_noaccess (T1, 180)
April results are round 1 of no_tool and of the tool scenario for the OLD models.

Safety:
  - The job list is fixed at the first launch in <root>/run_manifest.json (models, parts,
    each job's question list and checksum). Later launches must produce the identical plan
    or are refused; --status and --merge read the manifest and never re-plan or rewrite.
  - Question-list (pairs) files are written once, atomically, at the first launch.
  - One launcher per round (<root>/.launch.lock).
  - The root must be results_revision/run<N> (scratch roots must start with "_").
  - --merge builds <root>/merged_results.json from the cache files themselves (not from the
    per-job results.json, which can be incomplete after an interrupted resume) and refuses
    to write if any evaluation is duplicated; missing evaluations are listed (use
    --allow-incomplete to merge anyway).
  - Re-running the same command resumes: completed evaluations come from each job's cache;
    API errors (e.g. credit exhausted) are retried. Logs are appended.

Usage:
    python scripts/revision/run_revision.py --run 1 --dry-run     # plan and counts
    python scripts/revision/run_revision.py --run 1               # launch / resume
    python scripts/revision/run_revision.py --run 1 --status      # progress and spend
    python scripts/revision/run_revision.py --run 1 --merge       # write run1/merged_results.json
"""

import argparse
import csv
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from FlavorGraphTraverser.evaluation.utils.answer_parser import compute_question_score  # noqa: E402
NEW_MODELS = ("x-ai/grok-4.20", "mistralai/mistral-medium-3-5")
SLOW_FIRST = ("moonshotai/kimi-k2.5", "deepseek/deepseek-v3.2", "qwen/qwen3.5-397b-a17b")
FULL = ("no_tool", "tool_rerun", "tool_resolved", "graph_in_context")
MANIFEST = "run_manifest.json"


def enabled_models():
    cfg = yaml.safe_load(open(ROOT / "configs/models.yaml"))
    return [m["id"] for g in ("closed_source", "open_source") for m in cfg.get(g, []) if m.get("enabled")]


def prices():
    cfg = yaml.safe_load(open(ROOT / "configs/models.yaml"))
    return {m["id"]: m["pricing"] for g in ("closed_source", "open_source") for m in cfg.get(g, []) if m.get("pricing")}


def git_tag():
    h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return h + ("-dirty" if dirty else "")


def atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(text)
    os.replace(tmp, path)


def pairs_csv(model, cond, qids):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["model", "condition", "question_id"], lineterminator="\n")
    w.writeheader()
    w.writerows({"model": model, "condition": cond, "question_id": q} for q in qids)
    return buf.getvalue()


def job_name(model, cond, part=None):
    return f"{model.split('/')[1]}__{cond}" + (f"__part{part}" if part else "")


def plan(run, models, slow_chunks):
    """Pure planning (writes nothing). Returns a list of job dicts:
    {name, model, condition, part, questions (list or None = all), n}."""
    qs = [q["id"] for q in json.load(open(ROOT / "data/questions/benchmark_questions.json"))["questions"]]
    t1 = [q for q in qs if q.startswith("A")]
    fix = defaultdict(list)
    for r in csv.DictReader(open(ROOT / "results_revision/rerun_pairs.csv")):
        if r["purpose"] == "label_fix":
            fix[r["model"]].append(r["question_id"])
    base = []
    for m in models:
        if run == 1:
            if m in NEW_MODELS:
                base += [(m, c, None) for c in ("no_tool", "tool_rerun", "tool_resolved")]
            elif fix.get(m):
                base.append((m, "tool_resolved", fix[m]))
            base.append((m, "graph_in_context", None))
        else:
            base += [(m, c, None) for c in FULL]
        base.append((m, "prompt_only_noaccess", t1))
    jobs = []
    for m, c, sel in base:
        ids = sel if sel is not None else qs
        if m in SLOW_FIRST and slow_chunks > 1:
            for k in range(slow_chunks):
                part = ids[k::slow_chunks]
                if part:
                    jobs.append({"name": job_name(m, c, k + 1), "model": m, "condition": c, "part": k + 1,
                                 "questions": part, "n": len(part)})
        else:
            jobs.append({"name": job_name(m, c), "model": m, "condition": c, "part": None,
                         "questions": None if sel is None else ids, "n": len(ids)})
    jobs.sort(key=lambda j: (j["model"] not in SLOW_FIRST, j["model"], j["condition"], j["part"] or 0))
    for j in jobs:
        j["pairs"] = f"_pairs/{j['name']}.csv" if j["questions"] is not None else None
        j["sha"] = hashlib.sha256(json.dumps(j["questions"]).encode()).hexdigest()[:16]
    return jobs


def manifest_view(jobs):
    return [{k: j[k] for k in ("name", "model", "condition", "part", "pairs", "n", "sha")} for j in jobs]


def load_manifest(root):
    p = root / MANIFEST
    return json.loads(p.read_text()) if p.exists() else None


def cache_records(root, jobs):
    """{job name: [records]} read from each job's cache directory."""
    out = {}
    for j in jobs:
        files = glob.glob(str(root / j["name"] / "cache" / "**" / "*.json"), recursive=True)
        out[j["name"]] = [json.loads(Path(f).read_text()) for f in files]
    return out


def status(root, jobs):
    price = prices()
    recs = cache_records(root, jobs)
    done_n = exp_n = 0
    spend = 0.0
    errors = defaultdict(int)
    for j in jobs:
        rs = recs[j["name"]]
        for d in rs:
            if is_api_error(d):
                errors[j["model"].split("/")[1]] += 1
            mt = d.get("metrics") or {}
            p = price.get(d.get("model"))
            if p:
                spend += ((mt.get("input_tokens") or 0) * p["input"] + (mt.get("output_tokens") or 0) * p["output"]) / 1e6
        done_n += len(rs)
        exp_n += j["n"]
        print(f"  {j['name']:52} {len(rs):4}/{j['n']}")
    print(f"\nTotal {done_n:,}/{exp_n:,} evaluations; spend so far ${spend:.2f}")
    if errors:
        print("API errors (retried on re-launch):", dict(errors))


def is_api_error(d):
    """An evaluation cut off by an API failure: status api_error, or (results written before
    the multi-select / T3 status fix) an api_error entry in `errors` under another status."""
    return d.get("status") == "api_error" or any((e or {}).get("type") == "api_error" for e in d.get("errors") or [])


def merge(root, jobs, run, allow_incomplete=False):
    """Build <root>/merged_results.json from the cache files. Returns 0 on success."""
    recs = cache_records(root, jobs)
    seen = {}
    dups, missing, wrong_tag = [], [], []
    for j in jobs:
        rs = recs[j["name"]]
        expected = set(j["questions"]) if j["questions"] is not None else None
        got = set()
        for d in rs:
            key = (d["model"], d["condition"], d["question_id"])
            if key in seen:
                dups.append((key, seen[key], j["name"]))
                continue
            seen[key] = j["name"]
            got.add(d["question_id"])
            tag = (d.get("run_meta") or {}).get("run_tag") or ""
            if not tag.startswith(f"rev-run{run}-"):
                wrong_tag.append((key, tag))
            if is_api_error(d):
                missing.append((j["name"], d["question_id"], "api_error"))
        n_expected = len(expected) if expected is not None else j["n"]
        if len(got) < n_expected:
            missing.append((j["name"], f"{n_expected - len(got)} evaluations", "not run"))
    if dups:
        print(f"REFUSED: {len(dups)} duplicated evaluations, e.g. {dups[:3]}")
        return 1
    if wrong_tag:
        print(f"REFUSED: {len(wrong_tag)} results not tagged rev-run{run}-*, e.g. {wrong_tag[:3]}")
        return 1
    if missing and not allow_incomplete:
        print(f"REFUSED: round incomplete ({len(missing)} gaps), e.g. {missing[:5]}. "
              f"Resume the round, or pass --allow-incomplete.")
        return 1
    results = [d for j in jobs for d in recs[j["name"]]]
    for d in results:  # recompute from source fields, as the batch runner's cache loader does
        d["score"] = compute_question_score(model_answer=d.get("model_answer"), correct_answer=d.get("correct_answer"),
                                            is_correct=d.get("is_correct", False), judge_score=d.get("judge_score"),
                                            status=d.get("status", "success"))
    out = {"results": results,
           "run_status": "complete" if not missing else "incomplete",
           "summary": {"round": run, "evaluations": len(results), "jobs": len(jobs),
                       "merged_at": datetime.now().isoformat(timespec="seconds"), "source": "job caches"}}
    atomic_write(root / "merged_results.json", json.dumps(out, ensure_ascii=False))
    print(f"merged {len(results):,} evaluations from {len(jobs)} jobs into {root / 'merged_results.json'}"
          + (f" (INCOMPLETE: {len(missing)} gaps)" if missing else ""))
    return 0


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=int, choices=(1, 2, 3), required=True)
    ap.add_argument("--root", default=None, help="default: results_revision/run<N>; scratch roots must start with '_'")
    ap.add_argument("--models", nargs="*", default=None, help="default: enabled models in configs/models.yaml")
    ap.add_argument("--max-parallel", type=int, default=40)
    ap.add_argument("--slow-chunks", type=int, default=4,
                    help="split each job of the slow models (Kimi, DeepSeek, Qwen) into this many parallel parts")
    ap.add_argument("--max-questions", type=int, default=None, help="smoke tests only (scratch roots)")
    ap.add_argument("--allow-incomplete", action="store_true", help="--merge even if evaluations are missing")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--status", action="store_true")
    g.add_argument("--merge", action="store_true")
    args = ap.parse_args()

    root = (ROOT / (args.root or f"results_revision/run{args.run}")).resolve()
    rel = root.relative_to(ROOT.resolve())
    scratch = rel.name.startswith("_")
    if not scratch and rel != Path(f"results_revision/run{args.run}"):
        print(f"REFUSED: root for round {args.run} must be results_revision/run{args.run} "
              f"(or a scratch directory starting with '_'), got {rel}")
        return 1
    if args.max_questions and not scratch:
        print("REFUSED: --max-questions is for scratch roots only")
        return 1

    manifest = load_manifest(root)
    if args.status or args.merge:
        if manifest is None:
            print(f"No {MANIFEST} in {rel}: this round has not been launched.")
            return 1
        jobs = manifest["jobs"]
        for j in jobs:
            j["questions"] = None if j["pairs"] is None else \
                [r["question_id"] for r in csv.DictReader(open(root / j["pairs"]))]
        return status(root, jobs) or 0 if args.status else merge(root, jobs, args.run, args.allow_incomplete)

    models = args.models or enabled_models()
    jobs = plan(args.run, models, args.slow_chunks)
    if args.max_questions:
        for j in jobs:
            q = (j["questions"] or [x["id"] for x in json.load(open(ROOT / "data/questions/benchmark_questions.json"))["questions"]])
            j["questions"] = q[: args.max_questions]
            j["n"] = len(j["questions"])
            j["pairs"] = f"_pairs/{j['name']}.csv"
            j["sha"] = hashlib.sha256(json.dumps(j["questions"]).encode()).hexdigest()[:16]
    view = manifest_view(jobs)
    if manifest is not None and manifest["jobs"] != view:
        print(f"REFUSED: the plan differs from {rel}/{MANIFEST} (fixed at the first launch on "
              f"{manifest['created']}); same --models / --slow-chunks / rerun_pairs.csv are required to resume.")
        return 1

    tag = f"rev-run{args.run}-{git_tag()}"
    by_cond = defaultdict(int)
    for j in jobs:
        by_cond[j["condition"]] += j["n"]
    print(f"Round {args.run}: {len(jobs)} jobs, {sum(j['n'] for j in jobs):,} evaluations, root {rel}, run tag {tag}"
          + (" (resuming)" if manifest else ""))
    for c, n in sorted(by_cond.items()):
        print(f"  {c:22} {n:6,}")
    if tag.endswith("-dirty"):
        print("  NOTE: working tree has uncommitted changes; the run tag records this.")
    if args.dry_run:
        return 0

    lock = root / ".launch.lock"
    root.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        try:
            other = int(lock.read_text().strip())
        except ValueError:
            other = -1
        if other > 0 and pid_alive(other):
            print(f"REFUSED: another launcher (pid {other}) is running round {args.run}.")
            return 1
    lock.write_text(str(os.getpid()))
    try:
        if manifest is None:
            for j in jobs:
                if j["pairs"]:
                    atomic_write(root / j["pairs"], pairs_csv(j["model"], j["condition"], j["questions"]))
            atomic_write(root / MANIFEST, json.dumps({"round": args.run, "created": datetime.now().isoformat(timespec="seconds"),
                                                      "models": models, "slow_chunks": args.slow_chunks,
                                                      "first_run_tag": tag, "jobs": view}, indent=1))
        (root / "logs").mkdir(exist_ok=True)
        queue = list(jobs)
        running, failed = [], []
        while queue or running:
            while queue and len(running) < args.max_parallel:
                j = queue.pop(0)
                cmd = [sys.executable, str(ROOT / "scripts/experiment/run_experiment.py"), "--models", j["model"],
                       "--conditions", j["condition"], "--client", "openrouter", "--no-judge", "--no-merge",
                       "--yes", "--quiet", "--run-tag", tag, "--output", str(rel / j["name"])]
                if j["pairs"]:
                    cmd += ["--pairs", str(rel / j["pairs"])]
                log = open(root / "logs" / f"{j['name']}.log", "a")
                log.write(f"\n=== launch {datetime.now().isoformat(timespec='seconds')} tag {tag} ===\n")
                log.flush()
                running.append((subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT), log, j["name"]))
            time.sleep(5)
            still = []
            for p, log, name in running:
                if p.poll() is None:
                    still.append((p, log, name))
                else:
                    log.close()
                    print(f"  finished {name} (exit {p.returncode})", flush=True)
                    if p.returncode != 0:
                        failed.append((name, p.returncode))
            running = still
        status(root, jobs)
        if failed:
            print(f"\nJOBS WITH NON-ZERO EXIT ({len(failed)}): {failed} — check their logs, then re-launch to resume.")
    finally:
        if lock.exists() and lock.read_text().strip() == str(os.getpid()):
            lock.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
