#!/usr/bin/env python3
"""
Judge T3 (F-category) answers with the follow-up judge panel.

Panel: `revision_judges` in configs/models.yaml (Opus 5.5, Gemini 4 Argon, GPT-6.2 Sol).
Every judge scores every T3 answer. The judge prompt is the April prompt, unchanged
(prompts/judge_system.txt + LLMJudge._build_prompt + prompts/judge_closing.txt).

Storage. Result files are never modified (unlike scripts/run_judge.py, which writes
judge scores into the run caches). One JSON file per (judge, answer, slot):

    <out>/<judge-slug>/<slot>/<source>/<model-slug>/<condition>/<question_id>.json

  slot     "main" for the scores used in the paper; "repeat2" for the consistency re-judge
  source   run1 | run2 | run3 | run1_nemotron_tool | april

Each file holds the full judge transcript (system prompt, user prompt, response text,
reasoning text if returned), score and parse details, token usage, served model and
provider, request settings, a hash of the judged answer and of the prompt, timing and the
git commit. A file whose status is "success" or "parse_error" is final; "api_error" files
are retried on the next launch (e.g. after a credit top-up).

Answers judged (each must have a non-empty response text):
  run1, run2, run3          results_revision/run<N>/*/cache/**/F_*.json, run tag rev-run<N>-*
  run1_nemotron_tool        results_revision/run1_nemotron_tool/*/cache/**/F_*.json
  april                     results_revision/run1/original_run.json, the 9 models kept in the follow-up runs
                            (read-only)

Usage:
    python scripts/revision/run_judges.py --list                       # what would be judged
    python scripts/revision/run_judges.py --out results_revision/_judge_pilot --sample 20
    python scripts/revision/run_judges.py                               # full run, all judges
    python scripts/revision/run_judges.py --slot repeat2 --sample 100   # consistency check
    python scripts/revision/run_judges.py --status
"""

import argparse
import glob
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from FlavorGraphTraverser.evaluation.client import create_client  # noqa: E402
from FlavorGraphTraverser.evaluation.client.base import Message  # noqa: E402
from FlavorGraphTraverser.evaluation.judge.judge import JUDGE_SYSTEM_PROMPT, LLMJudge  # noqa: E402
from FlavorGraphTraverser.evaluation.utils.answer_parser import parse_judge_score  # noqa: E402

DEFAULT_OUT = "results_revision/judging"
SOURCES = ("run1", "run2", "run3", "run1_nemotron_tool", "april")
SLOTS = ("main", "repeat2")
FINAL = ("success", "parse_error")
MAX_TOKENS = 32768     # room for hidden reasoning; April needed 32k for Gemini
SAMPLE_SEED = 20261123
# April models kept in the follow-up runs (the two retired models and gpt-oss-20b are not).
APRIL_MODELS = (
    "anthropic/claude-sonnet-4.6", "openai/gpt-5.4", "google/gemini-3-flash-preview",
    "openai/gpt-oss-120b", "qwen/qwen3.5-397b-a17b", "moonshotai/kimi-k2.5",
    "meta-llama/llama-4-maverick", "deepseek/deepseek-v3.2", "nvidia/nemotron-3-super-120b-a12b")
APRIL_EXPECTED = 270   # 9 models x 2 conditions x 15 T3 questions
NEMOTRON = "nvidia/nemotron-3-super-120b-a12b"


def slug(model_id):
    return model_id.replace("/", "__")


def load_judges(path=ROOT / "configs/models.yaml"):
    return yaml.safe_load(open(path))["revision_judges"]


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha(text):
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def collect_answers(root=ROOT, april_models=APRIL_MODELS, april_expected=APRIL_EXPECTED):
    """All T3 answers to judge: list of dicts with source, model, condition, question_id, response.

    Nemotron's round-1 tool conditions come from run1_nemotron_tool (rerun fresh);
    its copies in run1 (the affected-rerun subset) are superseded and not judged."""
    out, seen = [], set()

    def add(source, r):
        text = r.get("model_response_text") or ""
        cut_off = r.get("status") == "api_error" or any(
            (e or {}).get("type") == "api_error" for e in r.get("errors") or [])
        if not text.strip() or cut_off:
            return
        key = (source, r["model"], r["condition"], r["question_id"])
        if key in seen:
            raise SystemExit(f"duplicate answer {key}")
        seen.add(key)
        out.append({"source": source, "model": r["model"], "condition": r["condition"],
                    "question_id": r["question_id"], "response": text})

    for n in (1, 2, 3):
        for f in sorted(glob.glob(str(root / f"results_revision/run{n}/*/cache/**/F_*.json"), recursive=True)):
            r = json.loads(Path(f).read_text())
            tag = (r.get("run_meta") or {}).get("run_tag") or ""
            if not tag.startswith(f"rev-run{n}-"):
                raise SystemExit(f"{f}: run tag {tag!r} does not belong to round {n}")
            if n == 1 and r["model"] == NEMOTRON and r["condition"] in ("tool_rerun", "tool_resolved"):
                continue
            add(f"run{n}", r)
    for f in sorted(glob.glob(str(root / "results_revision/run1_nemotron_tool/*/cache/**/F_*.json"), recursive=True)):
        add("run1_nemotron_tool", json.loads(Path(f).read_text()))
    n_april = 0
    for r in json.load(open(root / "results_revision/run1/original_run.json"))["results"]:
        if r["question_id"].startswith("F") and r["model"] in april_models:
            n_april += 1
            add("april", r)
    if april_expected is not None and n_april != april_expected:
        raise SystemExit(f"April: {n_april} T3 records for the kept models, expected {april_expected}")
    return out


def akey(a):
    return (a["source"], a["model"], a["condition"], a["question_id"])


def sample(answers, n, seed=SAMPLE_SEED):
    """Seeded sample, identical for every judge."""
    keys = sorted(answers, key=akey)
    return random.Random(seed).sample(keys, min(n, len(keys)))


def frozen_sample(answers, n, path):
    """Draw the sample once and store its keys; later launches reuse exactly those answers."""
    by_key = {akey(a): a for a in answers}
    if path.exists():
        keys = [tuple(k) for k in json.loads(path.read_text())["keys"]]
        missing = [k for k in keys if k not in by_key]
        if missing:
            raise SystemExit(f"{len(missing)} sampled answers no longer available, e.g. {missing[:2]}")
        if len(keys) != n:
            raise SystemExit(f"{path} holds a sample of {len(keys)}, not {n}")
        return [by_key[k] for k in keys]
    chosen = sample(answers, n)
    atomic_write(path, {"n": n, "seed": SAMPLE_SEED, "keys": [list(akey(a)) for a in chosen]})
    return chosen


def out_path(out, judge_id, slot, a):
    return (Path(out) / slug(judge_id) / slot / a["source"] / slug(a["model"]) / a["condition"]
            / f"{a['question_id']}.json")


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_record(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def is_final(path, answer_sha):
    """Final = a success/parse_error record for this exact answer text."""
    rec = read_record(path)
    return bool(rec) and rec.get("status") in FINAL and rec.get("answer_sha") == answer_sha


def served_ok(judge_id, served):
    """The served model must be the judge (OpenRouter may append a version suffix)."""
    return served is None or served == judge_id or served.startswith(judge_id + "-") or served.startswith(judge_id + ":")


def judge_one(client, judge, question, a, path, commit, parse_retries=2):
    """Judge one answer and write its record. Returns the record.

    A call that did not finish normally (finish_reason other than "stop", empty text, or a
    different served model) is stored as api_error and retried on the next launch, so a
    truncated judgment can never become a final score."""
    user_prompt = LLMJudge._build_prompt(None, question, a["response"])
    messages = [Message(role="system", content=JUDGE_SYSTEM_PROMPT), Message(role="user", content=user_prompt)]
    temperature = judge.get("temperature")
    old = read_record(path) or {}
    previous = (old.get("previous_attempts") or []) + (old.get("attempts") or [])
    attempts = []
    rec = None
    for attempt in range(parse_retries + 1):
        t0 = time.time()
        try:
            resp = client.query(messages, temperature=temperature, max_tokens=MAX_TOKENS)
        except Exception as e:  # client already retried transient errors
            attempts.append({"status": "api_error", "error": str(e)[:500]})
            rec = {"status": "api_error"}
            break
        text = resp.content or ""
        u = resp.usage
        base = {"response_text": text, "reasoning_text": resp.thinking_content, "finish_reason": resp.finish_reason,
                "usage": {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens} if u else None,
                "served_model": resp.resolved_model, "provider": resp.provider,
                "latency_s": round(time.time() - t0, 2)}
        problem = None
        if resp.finish_reason != "stop":
            problem = f"finish_reason={resp.finish_reason!r}"
        elif not text.strip():
            problem = "empty response"
        elif not served_ok(judge["id"], resp.resolved_model):
            problem = f"served model {resp.resolved_model!r}"
        if problem:
            attempts.append({"status": "api_error", "error": problem, **base})
            rec = {"status": "api_error"}
            break
        parsed = parse_judge_score(text)
        # A score found only by the last-digit fallback is not trusted (e.g. a degenerate
        # response): treated as unparsed, so the call is repeated.
        ok = parsed.score is not None and parsed.pattern_matched != "last digit"
        attempt_rec = {
            "status": "success" if ok else "parse_error",
            "score": parsed.score, "pattern_matched": parsed.pattern_matched, "matched_text": parsed.matched_text,
            "needs_review": parsed.pattern_matched == "last digit",
            **base,
        }
        attempts.append(attempt_rec)
        rec = attempt_rec
        if ok:
            break
    if rec["status"] == "parse_error":
        rec = dict(rec, score=None)
    final = {
        "judge_model": judge["id"], "judge_name": judge["name"], "judge_provider": judge["provider"],
        "source": a["source"], "model": a["model"], "condition": a["condition"], "question_id": a["question_id"],
        "answer_sha": sha(a["response"]), "prompt_sha": sha(JUDGE_SYSTEM_PROMPT + "\n\n" + user_prompt),
        "request": {"temperature": temperature, "temperature_sent": temperature is not None,
                    "max_tokens": MAX_TOKENS},
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "status": rec["status"], "score": rec.get("score"), "needs_review": bool(rec.get("needs_review")),
        "attempts": attempts,
        "previous_attempts": previous,   # earlier launches (api_error, or a since-changed answer)
        "usage_total": {k: sum((x.get("usage") or {}).get(k) or 0 for x in attempts + previous)
                        for k in ("input_tokens", "output_tokens")},
        "git_commit": commit, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    atomic_write(path, final)
    return final


def cost(rec, price):
    u = rec.get("usage_total") or {}
    return ((u.get("input_tokens") or 0) * price["input"] + (u.get("output_tokens") or 0) * price["output"]) / 1e6


def status(out, judges, slot):
    for j in judges:
        recs = [read_record(Path(f)) or {"status": "unreadable"}
                for f in glob.glob(str(Path(out) / slug(j["id"]) / slot / "**/*.json"), recursive=True)]
        c = Counter(r.get("status") for r in recs)
        spend = sum(cost(r, j["pricing"]) for r in recs)
        n_review = sum(bool(r.get("needs_review")) for r in recs)
        per = spend / len(recs) if recs else 0
        print(f"{j['name']:16} {slot}: {len(recs):5} files {dict(c)}  spend ${spend:.2f}"
              + (f"  (${per:.4f}/answer)" if recs else "") + (f"  {n_review} score(s) from the last-digit fallback" if n_review else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--slot", choices=SLOTS, default="main")
    ap.add_argument("--judges", nargs="*", help="judge ids (default: all revision_judges)")
    ap.add_argument("--sources", nargs="*", choices=SOURCES,
                    help="judge only these sources (default: all). Round 1 = run1 run1_nemotron_tool april")
    ap.add_argument("--sample", type=int, help="judge a seeded sample of N answers (pilot, repeat2)")
    ap.add_argument("--workers", type=int, default=8, help="parallel requests per judge")
    ap.add_argument("--list", action="store_true", help="print what would be judged and exit")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    out = (Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out).resolve()
    base = (ROOT / "results_revision").resolve()
    rel = out.relative_to(ROOT.resolve()) if out.is_relative_to(ROOT.resolve()) else out
    if out.parent != base or not (out.name == "judging" or out.name.startswith("_")):
        print(f"REFUSED: --out must be {DEFAULT_OUT} or results_revision/_<scratch> (got {rel})")
        return 1
    if args.slot == "repeat2" and not args.sample:
        print("REFUSED: --slot repeat2 needs --sample N")
        return 1
    judges = load_judges()
    if args.judges:
        unknown = set(args.judges) - {j["id"] for j in judges}
        if unknown:
            print(f"REFUSED: not in revision_judges: {sorted(unknown)}")
            return 1
        judges = [j for j in judges if j["id"] in args.judges]

    if args.status:
        status(out, judges, args.slot)
        return 0

    answers = collect_answers()
    if args.sources:
        answers = [a for a in answers if a["source"] in args.sources]
    if args.sample:
        answers = frozen_sample(answers, args.sample, out / f"sample_{args.slot}_{args.sample}.json")
    by_src = Counter(a["source"] for a in answers)
    print(f"{len(answers):,} answers to judge per judge: " + ", ".join(f"{k} {v}" for k, v in sorted(by_src.items())))
    print(f"judges: {', '.join(j['id'] for j in judges)}; slot {args.slot}; output {rel}")
    if args.list:
        return 0

    questions = {q["id"]: q for q in json.load(open(ROOT / "data/questions/benchmark_questions.json"))["questions"]}
    missing_q = {a["question_id"] for a in answers} - set(questions)
    if missing_q:
        print(f"REFUSED: questions missing from the benchmark file: {sorted(missing_q)[:5]}")
        return 1
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not set")
        return 1
    commit = git_commit()

    # Interleaved by answer, so every judge's requests run in parallel from the start.
    todo = [(j, a, out_path(out, j["id"], args.slot, a)) for a in answers for j in judges]
    stale = sum(1 for j, a, p in todo if (read_record(p) or {}).get("answer_sha") not in (None, sha(a["response"])))
    if stale:
        print(f"note: {stale} existing judgments are for an answer text that has since changed; re-judging them")
    todo = [t for t in todo if not is_final(t[2], sha(t[1]["response"]))]
    print(f"{len(todo):,} judge calls to make ({len(judges) * len(answers) - len(todo):,} already final)")
    if not todo:
        return 0
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        return 1

    lock = threading.Lock()
    counts, spend = defaultdict(Counter), defaultdict(float)
    clients = {j["id"]: threading.local() for j in judges}

    def work(j, a, path):
        local = clients[j["id"]]
        if not hasattr(local, "client"):
            local.client = create_client(client_type="openrouter", model=j["id"], api_key=api_key)
        rec = judge_one(local.client, j, questions[a["question_id"]], a, path, commit)
        with lock:
            counts[j["name"]][rec["status"]] += 1
            spend[j["name"]] += cost(rec, j["pricing"])
            done = sum(sum(c.values()) for c in counts.values())
            if done % 50 == 0 or done == len(todo):
                print(f"  {done:,}/{len(todo):,}  " + "  ".join(
                    f"{n}: {dict(c)} ${spend[n]:.2f}" for n, c in counts.items()), flush=True)
        return rec

    with ThreadPoolExecutor(max_workers=args.workers * len(judges)) as ex:
        futs = [ex.submit(work, *t) for t in todo]
        for f in as_completed(futs):
            f.result()
    print("done. " + "  ".join(f"{n}: {dict(c)} ${spend[n]:.2f}" for n, c in counts.items()))
    n_err = sum(c.get("api_error", 0) for c in counts.values())
    if n_err:
        print(f"{n_err} api_error records: launch again to retry them (e.g. after a credit top-up).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
