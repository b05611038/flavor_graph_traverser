#!/usr/bin/env bash
#
# Run full benchmark for all 11 models in parallel, then run LLM-as-judge.
#
# Each model gets its own output directory and log file.
# Results auto-merge into results/merged_results.json after each checkpoint
# so the auditor site updates live.
# After all models finish, judge pass runs automatically on F-category questions.
#
# Usage:
#   ./scripts/experiment/run_all.sh              # full benchmark + judge pass
#   ./scripts/experiment/run_all.sh --sample 3   # 3 questions per task type (smoke test)
#   ./scripts/experiment/run_all.sh --no-judge   # skip judge pass entirely
#   ./scripts/experiment/run_all.sh --judge-only # skip model eval, run judge only
#
# Logs: results/run_<timestamp>/logs/<model>.log
# Results: results/run_<timestamp>/<model>/results.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

# ── Parse flags ──────────────────────────────────────────────────────────────
SAMPLE_FLAG=""
JUDGE_FLAG="--no-judge"   # always skip inline judge; run standalone pass after
SKIP_EVAL=false
SKIP_JUDGE=false
EXTRA_FLAGS=""
YES=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sample)        SAMPLE_FLAG="--sample $2"; shift 2 ;;
        --no-judge)      SKIP_JUDGE=true;           shift   ;;
        --judge-only)    SKIP_EVAL=true;            shift   ;;
        --yes|-y)        YES=true;                  shift   ;;
        -h|--help)
            sed -n '2,20p' "$0"; exit 0 ;;
        *)
            EXTRA_FLAGS="$EXTRA_FLAGS $1"; shift ;;
    esac
done

# ── Config ────────────────────────────────────────────────────────────────────
RUN_TS="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="results/run_${RUN_TS}"
LOG_DIR="${RUN_DIR}/logs"
mkdir -p "$LOG_DIR"

QUESTIONS="data/questions/benchmark_questions.json"
GRAPH="data/graphs/coffee_flavor_wheel.json"

# Check API key
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    if [[ -f ".env" ]]; then
        export $(grep -E '^OPENROUTER_API_KEY=' .env | head -1) 2>/dev/null || true
    fi
fi
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "❌ OPENROUTER_API_KEY not set. Export it or add to .env" >&2
    exit 1
fi

# ── Model list: "model_id:short_name" pairs ───────────────────────────────────
MODELS=(
    "anthropic/claude-sonnet-4.6:claude-sonnet-4.6"
    "openai/gpt-5.4:gpt-5.4"
    "google/gemini-3-flash-preview:gemini-3-flash-preview"
    "x-ai/grok-4.1-fast:grok-4.1-fast"
    "openai/gpt-oss-120b:gpt-oss-120b"
    "qwen/qwen3.5-397b-a17b:qwen3.5-397b-a17b"
    "moonshotai/kimi-k2.5:kimi-k2.5"
    "meta-llama/llama-4-maverick:llama-4-maverick"
    "deepseek/deepseek-v3.2:deepseek-v3.2"
    "mistralai/mistral-medium-3.1:mistral-medium-3.1"
    "nvidia/nemotron-3-super-120b-a12b:nemotron-3-super-120b-a12b"
)

# ── Summary ───────────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════════════════════════"
echo " Full Benchmark Run"
echo "════════════════════════════════════════════════════════════════════════"
echo " Run dir:    $RUN_DIR"
echo " Questions:  $QUESTIONS"
echo " Models:     ${#MODELS[@]}"
echo " Conditions: no_tool  tool"
if [[ -n "$SAMPLE_FLAG" ]]; then
    echo " Mode:       SAMPLE ($SAMPLE_FLAG)"
else
    echo " Mode:       FULL (275 questions)"
fi
if $SKIP_JUDGE; then
    echo " Judge:      SKIP"
elif $SKIP_EVAL; then
    echo " Judge:      ONLY (skipping model eval)"
else
    echo " Judge:      after all models finish (scripts/run_judge.py)"
fi
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "Logs will be written to $LOG_DIR/<model>.log"
echo "Watch progress: ./scripts/audit/launch_auditor.sh"
echo ""

if ! $YES; then
    read -r -p "Press Enter to launch all models in parallel, or Ctrl+C to cancel... "
fi
echo ""

# ── Launch all models in parallel ─────────────────────────────────────────────
PIDS=()
MODEL_IDS=()

if $SKIP_EVAL; then
    echo "(Skipping model evaluation — running judge pass only)"
    echo ""
fi

if ! $SKIP_EVAL; then
    for entry in "${MODELS[@]}"; do
        model_id="${entry%%:*}"
        short="${entry##*:}"
        out_dir="${RUN_DIR}/${short}"
        log_file="${LOG_DIR}/${short}.log"

        echo "▶ Launching $short → $out_dir"

        python scripts/experiment/run_experiment.py \
            --client openrouter \
            --questions "$QUESTIONS" \
            --graph "$GRAPH" \
            --models "$model_id" \
            --conditions no_tool tool \
            --output "$out_dir" \
            --models-config configs/models.yaml \
            $SAMPLE_FLAG \
            $JUDGE_FLAG \
            $EXTRA_FLAGS \
            --yes \
            > "$log_file" 2>&1 &

        PIDS+=($!)
        MODEL_IDS+=("$short")
    done
fi

echo ""
echo "All ${#PIDS[@]} models launched. Waiting for completion..."
echo "(Tail any log: tail -f ${LOG_DIR}/<model>.log)"
echo ""

# ── Wait and report ───────────────────────────────────────────────────────────
FAILED=()
for i in "${!PIDS[@]}"; do
    pid="${PIDS[$i]}"
    short="${MODEL_IDS[$i]}"
    if wait "$pid"; then
        echo "  ✓ $short"
    else
        echo "  ✗ $short (exit $?)"
        FAILED+=("$short")
    fi
done

echo ""
echo "════════════════════════════════════════════════════════════════════════"
if [[ ${#FAILED[@]} -eq 0 ]]; then
    echo " ✓ ALL MODELS COMPLETE"
else
    echo " ✗ FAILED: ${FAILED[*]}"
    echo "   Re-run failed models individually — cache will resume from checkpoint"
fi
echo " Results: $RUN_DIR"
echo " Merged:  results/merged_results.json"
echo "════════════════════════════════════════════════════════════════════════"

# ── Judge pass ────────────────────────────────────────────────────────────────
if ! $SKIP_JUDGE; then
    echo ""
    echo "════════════════════════════════════════════════════════════════════════"
    echo " LLM-as-Judge Pass (F-category)"
    echo "════════════════════════════════════════════════════════════════════════"
    JUDGE_LOG="${LOG_DIR}/judge.log"
    echo " Judge log: $JUDGE_LOG"
    echo ""
    python scripts/run_judge.py --run "$RUN_DIR" --yes 2>&1 | tee "$JUDGE_LOG"
    echo ""
    echo "════════════════════════════════════════════════════════════════════════"
    echo " ✓ JUDGE PASS COMPLETE"
    echo "════════════════════════════════════════════════════════════════════════"
fi
