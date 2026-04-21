# Incident Memo: Premature Tool-Loop Exit Bug

**Date:** 2026-04-15  
**Severity:** High — affects 335/3025 (11.1%) of tool-condition cache entries  
**Status:** Bug fixed, affected cache cleared, re-run pending

---

## Root Cause

In `FlavorGraphTraverser/evaluation/evaluator.py`, `_evaluate_with_tools()`, the answer-check logic ran **before** checking whether the model had made a tool call:

```python
# BUGGY (before fix)
parse_result = parse_answer(response.content or "")
if parse_result.success:
    return parse_result.answer, ...   # ← exits even if tool call is pending

if response.tool_calls:
    ...  # ← tool never executed
```

`parse_answer()` uses a fallback pattern `\b([A-D])\b` ("Last letter") that matches any isolated letter A–D in the model's reasoning text. For example, the word "a" in "doesn't exist as a complete entry" matched as answer `A`, causing premature exit from the tool loop.

**Result:** The model's tool call was appended to `conversation_history` but never executed. The tool result was never returned to the model. The model never produced a final answer. The preamble text (e.g., "Great question! Let me analyze...") was captured as `model_response_text` and passed to the judge, which correctly scored it 0.

## Fix Applied

```python
# FIXED
if not response.tool_calls:          # only check for answer if no pending tool call
    parse_result = parse_answer(response.content or "")
    if parse_result.success:
        metrics.answered_early = (reasoning_calls < max_reasoning_calls)
        return parse_result.answer, parse_result, metrics, errors

if response.tool_calls:
    ...
```

File: `FlavorGraphTraverser/evaluation/evaluator.py`, method `_evaluate_with_tools()`.  
The ICL tool evaluator (`_evaluate_with_icl_tools`) was **not** affected — it already correctly checks for answer only in the `else` branch (when no tool call is detected).

---

## Scope of Impact

**335 tool-condition cache files** had truncated conversations (last message = assistant + pending tool call, no tool result, no final answer).

### By Model

| Model | Cut-off | Total tool | Rate |
|-------|---------|------------|------|
| deepseek-v3.2 | 212 | 275 | 77.1% |
| claude-sonnet-4.6 | 101 | 275 | 36.7% |
| kimi-k2.5 | 21 | 275 | 7.6% |
| mistral-medium-3.1 | 1 | 275 | 0.4% |
| All others | 0 | — | 0% |

Models unaffected: `gemini-3-flash-preview`, `gpt-5.4`, `gpt-oss-120b`, `grok-4.1-fast`, `llama-4-maverick`, `nemotron-3-super-120b-a12b`, `qwen3.5-397b-a17b`.

### By Question Type

| Task | Cut-off count |
|------|--------------|
| A1 (root classification, multi-select) | 82 |
| A2 (parent classification) | 78 |
| A4 (path validation, multi-select) | 52 |
| A3 (sibling/distance) | 40 |
| E2 (flavor matching) | 27 |
| E1 (closest descriptor) | 21 |
| A5 (LCA) | 11 |
| E3 (odd one out) | 12 |
| F (open-ended) | 12 |
| **Total** | **335** |

### By Model × Task

| Model / Task | Count |
|-------------|-------|
| deepseek-v3.2 / A2 | 49 |
| deepseek-v3.2 / A1 | 45 |
| deepseek-v3.2 / A4 | 28 |
| deepseek-v3.2 / A3 | 23 |
| deepseek-v3.2 / E2 | 23 |
| deepseek-v3.2 / E1 | 20 |
| claude-sonnet-4.6 / A1 | 33 |
| claude-sonnet-4.6 / A4 | 23 |
| claude-sonnet-4.6 / A3 | 16 |
| claude-sonnet-4.6 / A2 | 15 |
| deepseek-v3.2 / A5 | 9 |
| kimi-k2.5 / A2 | 14 |
| deepseek-v3.2 / E3 | 10 |
| deepseek-v3.2 / F | 5 |
| claude-sonnet-4.6 / F | 5 |
| claude-sonnet-4.6 / E2 | 4 |
| kimi-k2.5 / A1 | 3 |
| claude-sonnet-4.6 / E3 | 2 |
| claude-sonnet-4.6 / A5 | 2 |
| kimi-k2.5 / F | 2 |
| claude-sonnet-4.6 / E1 | 1 |
| kimi-k2.5 / A3 | 1 |
| kimi-k2.5 / A4 | 1 |
| mistral-medium-3.1 / A1 | 1 |

---

## Data Actions Taken

- **Archived** 335 cut-off cache files to `data/backups/cutoff_tool_responses_20260415/` (preserving original directory structure)
- **Removed** 335 files from `results/run_20260413_141616/` cache directories
- The batch runner will treat these as unprocessed and re-evaluate them on the next run

---

## Cost Estimate for Re-run

The 335 questions need to be re-evaluated under the tool condition only. Re-run costs depend on which models need re-evaluation.

Approximate token counts per question (tool condition with 2–4 tool turns):
- ~3,000–5,000 input tokens, ~500–800 output tokens

Estimated OpenRouter costs:

| Model | Questions | Approx. cost |
|-------|-----------|-------------|
| deepseek-v3.2 | 212 | ~$1–3 |
| claude-sonnet-4.6 | 101 | ~$2–5 |
| kimi-k2.5 | 21 | ~$0.5–1 |
| mistral-medium-3.1 | 1 | negligible |
| **Total** | **335** | **~$5–10** |

F-category questions (12 total, across 3 models) will also need re-judging after re-evaluation. At ~$0.28/question for GPT-5.4 Pro judge: ~$3.36 additional. Opus and Gemini judges are cheaper.

**Recommended top-up: $15–20** to cover re-run + re-judging with comfortable margin.

---

## Next Steps

1. Top up OpenRouter account ($15–20 recommended)
2. Re-run batch evaluation for affected models/conditions:
   ```bash
   python scripts/run_experiment.py --models deepseek-v3.2 claude-sonnet-4.6 kimi-k2.5 mistral-medium-3.1 --conditions tool
   ```
3. Re-run judge for newly evaluated F-category questions:
   ```bash
   python scripts/run_judge.py --judge-model anthropic/claude-opus-4.6
   python scripts/run_judge.py --judge-model google/gemini-3.1-pro-preview --max-tokens 32768
   python scripts/run_judge.py --judge-model openai/gpt-5.4-pro --max-tokens 16384
   ```
4. Rebuild results:
   ```bash
   python scripts/rebuild_results.py
   ```
