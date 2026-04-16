#!/usr/bin/env python3
"""
Standalone LLM-as-a-Judge runner for F-category questions.

Supports a multi-judge panel: each judge model stores its score separately
under `judge_scores[model_id]`. The final `score` field is the mean across
all judges that have run so far. Running a second judge on already-judged
files will add its score without overwriting the first.

Features:
  - Multi-judge: scores stored per model in judge_scores dict
  - Resume-safe: skips files already scored by THIS judge model
  - Retry logic: up to 3 attempts per question on API/parse errors
  - Atomic cache updates: write to tmp then rename
  - Dry-run mode: preview scope without spending tokens

Usage:
    python scripts/run_judge.py
    python scripts/run_judge.py --run results/merge_all
    python scripts/run_judge.py --judge-model anthropic/claude-opus-4.6
    python scripts/run_judge.py --judge-model google/gemini-3.1-pro-preview
    python scripts/run_judge.py --judge-model openai/gpt-5.4-pro
    python scripts/run_judge.py --filter-models claude-sonnet-4.6 gpt-5.4
    python scripts/run_judge.py --dry-run
"""

import argparse
import glob
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Load .env if present
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser.evaluation.judge.judge import LLMJudge
from FlavorGraphTraverser.evaluation.client import create_client


RETRY_BACKOFF = [5, 15, 30]  # seconds between retries


def find_f_cache_files(run_dir: str) -> list[Path]:
    """Find all F-category cache files across all models/conditions."""
    patterns = [
        f"{run_dir}/*/cache/**/F_*.json",
        f"{run_dir}/*/*/cache/**/F_*.json",
    ]
    files = []
    for pat in patterns:
        files.extend(Path(p) for p in glob.glob(pat, recursive=True))
    return sorted(set(files))


def load_questions(questions_path: str) -> dict:
    """Load questions indexed by question_id."""
    raw = json.loads(Path(questions_path).read_text())
    questions = raw.get("questions", raw) if isinstance(raw, dict) else raw
    return {q["id"]: q for q in questions}


def update_cache_atomic(path: Path, updates: dict):
    """Update a cache file atomically: write tmp then rename."""
    data = json.loads(path.read_text())
    data.update(updates)
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


def compute_mean_score(judge_scores: dict) -> float:
    """Compute mean score across all judges that returned a valid score."""
    valid = [v for v in judge_scores.values() if v is not None]
    return (sum(valid) / len(valid) / 5.0) if valid else 0.0


def run_judge_on_file(
    cache_path: Path,
    judge: LLMJudge,
    judge_model: str,
    questions: dict,
    max_retries: int = 3,
    dry_run: bool = False,
) -> str:
    """
    Run a single judge model on one cache file.

    Scores are stored under judge_scores[judge_model]. The top-level `score`
    field is updated to the mean across all judges.

    Returns: "skipped", "ok", "parse_error", "api_error", "no_question"
    """
    data = json.loads(cache_path.read_text())

    # Skip if THIS judge has already attempted this file (score=None means failed but recorded)
    judge_scores = data.get("judge_scores", {})
    if judge_model in judge_scores:
        return "skipped"

    # Also skip if cache was marked as having no matching question
    if data.get("status") == "no_question":
        return "skipped"

    # Skip if model never produced a response
    model_response = data.get("model_response_text") or ""
    if not model_response.strip():
        return "skipped"

    question_id = data.get("question_id", "")
    question = questions.get(question_id)
    if question is None:
        # Mark in cache so resume runs don't re-scan this file
        update_cache_atomic(cache_path, {"status": "no_question"})
        return "no_question"

    if dry_run:
        return "dry_run"

    # Retry loop
    for attempt in range(max_retries):
        try:
            result = judge.evaluate(question, model_response)

            if result.status == "success":
                judge_scores[judge_model] = result.score
                mean_score = compute_mean_score(judge_scores)

                judge_results = data.get("judge_results", {})
                judge_results[judge_model] = {
                    "score": result.score,
                    "judge_response": result.judge_response,
                    "status": result.status,
                    "pattern_matched": result.parse_result.pattern_matched,
                }
                update_cache_atomic(cache_path, {
                    "judge_scores": judge_scores,
                    "judge_results": judge_results,
                    "status": "success",
                    "score": mean_score,
                })
                return "ok"

            elif result.status == "parse_error":
                if attempt < max_retries - 1:
                    print(f"      parse_error (attempt {attempt+1}), retrying...")
                    time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF)-1)])
                    continue
                # Record parse_error for this judge without touching other judges
                # Mark judge_scores[model] = None so resume skips this file
                judge_scores[judge_model] = None
                judge_results = data.get("judge_results", {})
                judge_results[judge_model] = {
                    "score": None,
                    "judge_response": result.judge_response,
                    "status": "parse_error",
                }
                update_cache_atomic(cache_path, {
                    "judge_scores": judge_scores,
                    "judge_results": judge_results,
                    "status": "judge_parse_error",
                })
                return "parse_error"

            elif result.status == "api_error":
                if attempt < max_retries - 1:
                    wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF)-1)]
                    print(f"      api_error (attempt {attempt+1}): {result.error}. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                # Exhausted retries — mark in cache so resume doesn't retry forever
                judge_scores[judge_model] = None
                judge_results = data.get("judge_results", {})
                judge_results[judge_model] = {"score": None, "status": "api_error"}
                update_cache_atomic(cache_path, {
                    "judge_scores": judge_scores,
                    "judge_results": judge_results,
                })
                return "api_error"

        except Exception as e:
            if attempt < max_retries - 1:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF)-1)]
                print(f"      exception (attempt {attempt+1}): {e}. Waiting {wait}s...")
                time.sleep(wait)
                continue
            # Exhausted retries — mark in cache
            judge_scores[judge_model] = None
            judge_results = data.get("judge_results", {})
            judge_results[judge_model] = {"score": None, "status": "exception", "error": str(e)}
            update_cache_atomic(cache_path, {
                "judge_scores": judge_scores,
                "judge_results": judge_results,
            })
            return "api_error"

    return "api_error"


def main():
    parser = argparse.ArgumentParser(description="Run LLM judge panel on F-category cache files")
    parser.add_argument("--run", default="results/merge_all",
                        help="Run directory to scan")
    parser.add_argument("--questions", default="data/questions/benchmark_questions.json",
                        help="Questions file")
    parser.add_argument("--judge-model", default="anthropic/claude-opus-4.6",
                        help="Judge model to run (default: anthropic/claude-opus-4.6)")
    parser.add_argument("--filter-models", nargs="+",
                        help="Only judge responses from these evaluated models (substring match)")
    parser.add_argument("--max-tokens", type=int, default=8192,
                        help="Max output tokens for judge response (default: 8192; use 32768+ for Gemini)")
    parser.add_argument("--max-retries", type=int, default=3,
                        help="Max retries per question (default: 3)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview scope without making API calls")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation prompts (for scripted use)")
    args = parser.parse_args()

    print(f"Run dir:     {args.run}")
    print(f"Judge model: {args.judge_model}")
    print(f"Dry run:     {args.dry_run}")
    print()

    # Load questions
    questions = load_questions(args.questions)
    print(f"Loaded {len(questions)} questions")

    # Find F-category cache files
    all_files = find_f_cache_files(args.run)
    print(f"Found {len(all_files)} F-category cache files")

    # Filter by evaluated model if requested
    if args.filter_models:
        all_files = [f for f in all_files if any(m in str(f) for m in args.filter_models)]
        print(f"Filtered to {len(all_files)} files matching {args.filter_models}")

    # Categorize: needs judging by THIS judge vs already done
    needs_judge = []
    already_done = 0
    no_response = 0
    for f in all_files:
        data = json.loads(f.read_text())
        judge_scores = data.get("judge_scores", {})
        if args.judge_model in judge_scores:
            already_done += 1
        elif data.get("status") in ("no_question", "judge_parse_error"):
            # Already attempted and recorded — skip without re-processing
            already_done += 1
        elif not (data.get("model_response_text") or "").strip():
            no_response += 1
        else:
            needs_judge.append(f)

    print(f"\nAlready judged by {args.judge_model}: {already_done}")
    print(f"No response:    {no_response}")
    print(f"To judge:       {len(needs_judge)}")

    if not needs_judge:
        print("\n✓ Nothing to judge.")
        return

    # Estimate cost (Claude Opus 4.6: $15/M input, $75/M output)
    # ~1500 input tokens (question + rubric + model response) + ~800 output tokens
    est_input = len(needs_judge) * 1500 / 1e6
    est_output = len(needs_judge) * 800 / 1e6
    est_cost = est_input * 15 + est_output * 75
    print(f"Estimated cost: ~${est_cost:.2f} ({len(needs_judge)} calls × ~2300 tok)")

    if args.dry_run:
        print("\n[Dry run] Files that would be judged:")
        for f in needs_judge[:20]:
            parts = f.parts
            print(f"  {'/'.join(parts[-4:])}")
        if len(needs_judge) > 20:
            print(f"  ... and {len(needs_judge)-20} more")
        return

    # Create judge
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    judge_client = create_client(
        client_type="openrouter",
        model=args.judge_model,
        api_key=api_key,
    )
    judge = LLMJudge(judge_client, temperature=0.0, max_tokens=args.max_tokens)
    print(f"\nStarting judge pass...\n")

    # Run
    counts = {"ok": 0, "parse_error": 0, "api_error": 0, "no_question": 0}
    for i, cache_path in enumerate(needs_judge, 1):
        parts = cache_path.parts
        label = "/".join(parts[-4:])
        print(f"  [{i}/{len(needs_judge)}] {label} ... ", end="", flush=True)

        status = run_judge_on_file(
            cache_path, judge, args.judge_model, questions,
            max_retries=args.max_retries,
        )
        counts[status] = counts.get(status, 0) + 1

        symbol = {"ok": "✓", "parse_error": "⚠", "api_error": "✗", "no_question": "?"}.get(status, status)
        print(symbol)

    print(f"\n{'='*50}")
    print(f"Done: {counts.get('ok',0)} judged | {counts.get('parse_error',0)} parse errors | "
          f"{counts.get('api_error',0)} API errors | {counts.get('no_question',0)} missing questions")


if __name__ == "__main__":
    main()
