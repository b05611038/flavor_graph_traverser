#!/usr/bin/env bash
#
# Launch the unified question auditor / results review site.
#
# Defaults:
#   Questions: data/questions/all_questions_system.json
#   Results:   auto-merges ALL results/*/results.json into results/merged_results.json
#   Port:      5000  (hardcoded inside the Python script)
#
# Override with env vars or flags:
#   QUESTIONS=path/to/questions.json RESULTS=path/to/results.json ./launch_auditor.sh
#   ./launch_auditor.sh --questions path/to/q.json --results path/to/r.json
#   ./launch_auditor.sh --no-merge   # skip merge, use newest experiment_*/results.json only
#
# Run from anywhere — paths are resolved relative to the repo root.

set -euo pipefail

# Resolve repo root (this script lives at <repo>/scripts/audit/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# --- Defaults ---
QUESTIONS="${QUESTIONS:-data/questions/all_questions_system.json}"
RESULTS="${RESULTS:-}"
NO_MERGE=false

# --- Parse CLI overrides ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --questions) QUESTIONS="$2"; shift 2 ;;
        --results)   RESULTS="$2";   shift 2 ;;
        --no-merge)  NO_MERGE=true;  shift   ;;
        -h|--help)
            sed -n '2,20p' "$0"
            exit 0 ;;
        *)
            echo "Unknown arg: $1" >&2
            exit 2 ;;
    esac
done

# --- Sanity checks ---
if [[ ! -f "$QUESTIONS" ]]; then
    echo "❌ Questions file not found: $QUESTIONS" >&2
    exit 1
fi

# --- Resolve results file ---
if [[ -z "$RESULTS" ]]; then
    if $NO_MERGE; then
        # Fall back to newest experiment_*/results.json
        RESULTS="$(ls -1dt results/experiment_*/results.json 2>/dev/null | head -n 1 || true)"
    else
        # Auto-merge all results/*/results.json into a single file
        MERGED="results/merged_results.json"
        echo "↻ Merging all results → $MERGED"
        python3 - "$MERGED" <<'PYEOF'
import sys, json, glob, os
from pathlib import Path

out_path = sys.argv[1]

patterns = [
    "results/*/results.json",
    "results/*/*/results.json",   # nested dirs like results/run_*/model/
]

files = []
for pat in patterns:
    files.extend(glob.glob(pat))

# Sort oldest→newest so the most recent run overwrites older smoke-test data
files.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)

merged_map = {}  # (question_id, model, condition) → result (last writer wins)
loaded = 0
for path in files:
    try:
        with open(path) as f:
            data = json.load(f)
        for r in data.get("results", []):
            key = (r.get("question_id"), r.get("model"), r.get("condition"))
            if None not in key:
                merged_map[key] = r
        loaded += 1
    except Exception as e:
        print(f"  ⚠ Skipping {path}: {e}", file=sys.stderr)

all_results = list(merged_map.values())

merged = {
    "run_status": "merged",
    "summary": {
        "total_evaluations": len(all_results),
        "source": f"auto-merged from {loaded} results files",
    },
    "results": all_results,
}

Path(out_path).parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    json.dump(merged, f, indent=2)

models = sorted({r.get("model", "") for r in all_results})
conditions = sorted({r.get("condition", "") for r in all_results})
print(f"  {len(all_results)} records | {len(models)} models | {len(conditions)} conditions")
for m in models:
    count = sum(1 for r in all_results if r.get("model") == m)
    print(f"    {m}: {count}")
PYEOF
        RESULTS="$MERGED"
    fi
fi

if [[ -n "$RESULTS" && ! -f "$RESULTS" ]]; then
    echo "⚠ Results file not found: $RESULTS  (continuing without results)" >&2
    RESULTS=""
fi

# --- Free port 5000 if held ---
PORT=5000
if lsof -ti:"$PORT" >/dev/null 2>&1; then
    echo "↻ Port $PORT in use — killing existing process(es)"
    lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# --- Launch ---
echo "Repo:      $REPO_ROOT"
echo "Questions: $QUESTIONS"
if [[ -n "$RESULTS" ]]; then
    echo "Results:   $RESULTS"
    exec python scripts/audit/question_auditor_unified.py "$QUESTIONS" --results "$RESULTS"
else
    echo "Results:   (none — review/audit modes only)"
    exec python scripts/audit/question_auditor_unified.py "$QUESTIONS"
fi
