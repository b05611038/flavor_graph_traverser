# FlavorGraphTraverser: Implementation Guide

> **Summary of all design decisions and implementation requirements**  
> Last Updated: 2026-01-30

---

## Table of Contents

1. [Research Overview](#1-research-overview)
2. [Experimental Conditions](#2-experimental-conditions)
3. [Models](#3-models)
4. [Tool Interface Design](#4-tool-interface-design)
5. [Turn Structure](#5-turn-structure)
6. [Questions Dataset](#6-questions-dataset)
7. [Function Calling Compatibility](#7-function-calling-compatibility)
8. [Caching Strategy](#8-caching-strategy)
9. [Error Handling](#9-error-handling)
10. [Logging & File Output](#10-logging--file-output)
11. [Implementation Reminders](#11-implementation-reminders)
12. [Budget Estimate](#12-budget-estimate)
13. [Testing Strategy](#13-testing-strategy)
14. [Placeholder Items](#14-placeholder-items)

---

## 1. Research Overview

### Research Question

For domain-specific hierarchical reasoning, how does tool-augmented inference compare to direct prompting?

### Thesis

Tool-augmented LLMs achieve near-full-context accuracy with significantly lower token cost, making them practical for deployable sensory recommendation systems.

### Key Comparisons

- **C2 vs C0**: How much do tools help?
- **C1 vs C0**: Does structural hint alone help without tools?
- **C3 vs C2**: Does CoT improve tool-augmented reasoning?

---

## 2. Experimental Conditions

### 4 Conditions (C0-C3)

| Condition | Tools | CoT | Max Reasoning Calls | Description |
|-----------|-------|-----|---------------------|-------------|
| **C0** | ✗ | ✗ | - | Zero-shot baseline |
| **C1** | ✗ | ✓ | - | CoT with structural hint |
| **C2** | ✓ | ✗ | 3 | Tools only |
| **C3** | ✓ | ✓ | 3 | CoT + Tools |

### CoT Prompt

```
Flavor descriptors are organized in a hierarchical graph structure 
(e.g., 'strawberry' → 'berry' → 'fruity'). Let's think step-by-step.
```

### Removed Conditions (with rationale)

- **Original C1 (few-shot)**: Removed - meaningful examples leak graph structure, selection bias, overlap with test questions
- **C5 (full context)**: Removed - unfair comparison, tests graph reading ability rather than reasoning

---

## 3. Models

### 11 Models Total (4 Closed + 7 Open)

#### Closed-Source (4) - Mid-tier "everyday use" models

| Provider | Model | OpenRouter ID | Pricing (in/out per 1M) |
|----------|-------|---------------|-------------------------|
| Anthropic | Claude Sonnet 4.5 | `anthropic/claude-sonnet-4.5` | $3 / $15 |
| OpenAI | GPT-5.2 | `openai/gpt-5.2` | $1.75 / $14 |
| Google | Gemini 3 Flash | `google/gemini-3-flash-preview` | $0.50 / $3 |
| xAI | Grok 4.1 Fast | `xai/grok-4-1-fast` | $0.20 / $0.50 |

#### Open-Source (7)

| Provider | Model | OpenRouter ID |
|----------|-------|---------------|
| OpenAI | GPT-OSS 120B | `openai/gpt-oss-120b` |
| Alibaba | Qwen3-235B-A22B | `qwen/qwen3-235b-a22b-instruct` |
| Moonshot | Kimi K2 | `moonshotai/kimi-k2` |
| Meta | Llama 4 Maverick | `meta-llama/llama-4-maverick` |
| DeepSeek | DeepSeek Chat | `deepseek/deepseek-chat` |
| Mistral | Mistral Medium 3 | `mistralai/mistral-medium-3` |
| NVIDIA | Nemotron Super 49B | `nvidia/llama-3.3-nemotron-super-49b-v1` |

#### Geographic Coverage

- **US**: Anthropic, OpenAI, Google, xAI, Meta, NVIDIA
- **EU**: Mistral
- **China**: Qwen, Kimi, DeepSeek

---

## 4. Tool Interface Design

### Critical Innovation: Batch Validation

**Problem**: Models penalized for descriptor name mismatches (e.g., "Rose" vs "rose") rather than reasoning failures.

**Solution**: Separate free validation tool from counted reasoning tools.

### Tool Definitions

| Tool | Purpose | Cost | Limit | Batch Size |
|------|---------|------|-------|------------|
| `validate_descriptors` | Check descriptor existence | **Free** | Unlimited calls | Max 10 items/call |
| `get_parent` | Query parent node | Counted | 3 total (shared) | Single |
| `get_children` | Query children nodes | Counted | 3 total (shared) | Single |

### Fairness Principle

- Validation reveals only **existence**, NOT relationships
- Model must still strategize which descriptors to query
- Name matching is separated from reasoning ability

---

## 5. Turn Structure

### Flow Diagram

```
Start
  │
  ▼
┌─────────────────────────────────────┐
│ Show: Problem + Tools               │
│ Model: validate_descriptors([...])  │  ← Free
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ Show: Problem + Validation Result   │
│ Model: get_parent("x")              │  ← Reasoning #1
│    OR: Answer directly              │
└─────────────────────────────────────┘
  │
  ▼ (if tool called)
┌─────────────────────────────────────┐
│ Show: Problem + History             │
│ Model: validate_descriptors([...])  │  ← Free (optional)
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ Show: Problem + All History         │
│ Model: get_children("y")            │  ← Reasoning #2
│    OR: Answer directly              │
└─────────────────────────────────────┘
  │
  ▼ (if tool called)
  ... (repeat until answer or #3)
  │
  ▼
┌─────────────────────────────────────┐
│ After Reasoning #3:                 │
│ "Provide your final answer now"     │
│ Model: MUST answer                  │
└─────────────────────────────────────┘
```

### Key Rules

| Aspect | Rule |
|--------|------|
| `validate_descriptors` | Free, optional at start of each reasoning turn |
| `get_parent` / `get_children` | Counted, max 3 total (shared limit) |
| Answer | Can come anytime, or forced after 3 reasoning calls |

---

## 6. Questions Dataset

### Overview

| Category | Task Type | Count | Evaluation |
|----------|-----------|-------|------------|
| **A** | Taxonomic Reasoning | 180 | Exact match |
| **E** | Similarity Reasoning | 80 | Exact match |
| **F** | Open Reasoning | 10-15 | LLM-as-judge |
| | **Total** | **~275** | |

### Task Breakdown

#### Category A: Taxonomic Reasoning (180)

- A1: Root Classification (50)
- A2: Ancestor Verification (50)
- A3: Sibling Identification (30)
- A4: Path Reconstruction (30)
- A5: Lowest Common Ancestor (20)

#### Category E: Similarity Reasoning (80)

- E1: Similarity Ranking (30)
- E2: Pairwise Comparison (30)
- E3: Odd One Out (20)

#### Category F: Open Reasoning (10-15)

- LLM-judged with rubric
- Judge model: `anthropic/claude-opus-4.5`

### Answer Extraction

```python
# Priority order:
1. r"I select \(([A-D])\)"           # Primary
2. r"answer is \(([A-D])\)"          # Fallback 1
3. Last standalone (X) in response   # Fallback 2
4. Last standalone letter A/B/C/D    # Fallback 3
5. None found → parse_error          # Mark as incorrect
```

---

## 7. Function Calling Compatibility

### Strategy

1. **Trust OpenRouter** to normalize function calling formats
2. **Pilot test** each model before full run
3. **Fallback**: Mark as `tool_error` if function call fails

### Known Considerations

| Model | Notes |
|-------|-------|
| Llama 4 Maverick | Uses pythonic parser (medium reliability) |
| Nemotron Super 49B | May have tool calling issues |
| All closed-source | Native support, high reliability |

---

## 8. Caching Strategy

### Directory Structure

```
results/cache/{model}/{condition}/{question_id}.json
```

### Cache Schema

```json
{
  "question_id": "A1_001",
  "model": "anthropic/claude-sonnet-4.5",
  "condition": "C2",
  "run_id": "2026-01-30_14-30-00",
  "timestamp": "2026-01-30T14:30:10Z",
  
  "question": {
    "text": "Which root category does 'jasmine' belong to?",
    "options": {"A": "fruity", "B": "floral", "C": "sweet", "D": "spicy"},
    "correct": "B"
  },
  
  "result": {
    "final_answer": "B",
    "is_correct": true,
    "status": "success"
  },
  
  "metrics": {
    "total_tokens": {"input": 800, "output": 150},
    "reasoning_calls": 2,
    "validation_calls": 1,
    "total_turns": 3,
    "answered_early": true,
    "total_latency_ms": 4679
  },
  
  "errors": []
}
```

### Resume Support

- Check cache before running each question
- Skip if valid cache exists
- Re-run only on explicit request or version bump

---

## 9. Error Handling

### Error Types and Handling

| Error Type | Detection | Handling | Logging |
|------------|-----------|----------|---------|
| **API timeout** | Request exceeds 60s | Retry 3× (2s, 4s, 8s backoff) | Log attempt count |
| **Rate limit (429)** | HTTP 429 | Wait `Retry-After`, then retry | Log wait time |
| **API error (5xx)** | HTTP 5xx | Retry 3× with backoff | Log error code |
| **Invalid JSON** | Parse fails | Retry once, then `parse_error` | Log raw response |
| **No tool call** | Text instead of tool | Treat as direct answer attempt | Log behavior |
| **Invalid tool format** | Missing fields | Attempt repair once, else `tool_error` | Log malformed call |
| **Invalid descriptor** | Descriptor not in graph | Return error to model, count as reasoning call | Log mismatch |
| **Model refusal** | Refuses to answer | Mark as `refusal`, count as incorrect | Log refusal text |
| **Answer extraction fail** | Can't extract A/B/C/D | Mark as `parse_error`, count as incorrect | Log full response |
| **Max retries exceeded** | 3 retries failed | Mark as `api_error`, skip question | Log all attempts |

### Error Schema

```json
{
  "errors": [
    {
      "turn": 2,
      "phase": "reasoning",
      "error_type": "rate_limit",
      "message": "429 Too Many Requests",
      "retry_count": 2,
      "resolved": true
    }
  ],
  "final_status": "success" | "parse_error" | "api_error" | "refusal" | "tool_error"
}
```

---

## 10. Logging & File Output

### Log Destinations

| Type | Purpose | Path |
|------|---------|------|
| **Experiment Log** | High-level progress | `logs/{run_id}/experiment.log` |
| **Turn Log** | Detailed per-turn | `logs/{run_id}/turns/{model}/{condition}/{question_id}.jsonl` |
| **Result Cache** | For resume/analysis | `results/cache/{model}/{condition}/{question_id}.json` |
| **Summary** | Aggregated metrics | `results/{run_id}/summary.csv` |
| **Config Copy** | Reproducibility | `logs/{run_id}/config.yaml` |

### Directory Structure

```
project/
├── logs/
│   └── {run_id}/
│       ├── experiment.log
│       ├── config.yaml
│       └── turns/
│           └── {model}/
│               └── {condition}/
│                   └── {question_id}.jsonl
│
├── results/
│   ├── cache/
│   │   └── {model}/
│   │       └── {condition}/
│   │           └── {question_id}.json
│   │
│   └── {run_id}/
│       ├── summary.csv
│       └── errors.csv
```

### Standard Field Names

Use these consistently across all files:

```python
# Identifiers
"run_id"          # e.g., "2026-01-30_14-30-00"
"model"           # e.g., "anthropic/claude-sonnet-4.5"
"condition"       # e.g., "C2"
"question_id"     # e.g., "A1_001"

# Question fields
"category"        # "A", "E", "F"
"task"            # "A1", "A2", ..., "E1", "E2", "E3", "F"
"question_text"
"options"         # {"A": "...", "B": "...", ...}
"correct_answer"  # "A", "B", "C", or "D"

# Result fields
"model_answer"    # "A", "B", "C", "D", or null
"is_correct"      # true/false
"status"          # "success", "parse_error", "api_error", "refusal", "tool_error"

# Metrics
"reasoning_calls" # 0, 1, 2, or 3
"validation_calls"
"total_turns"
"input_tokens"
"output_tokens"
"latency_ms"

# Turn-level fields
"turn_number"     # 1, 2, 3, ...
"phase"           # "validation", "reasoning", "answer"
"tool_name"       # "validate_descriptors", "get_parent", "get_children", null
"tool_args"
"tool_result"
```

---

## 11. Implementation Reminders

### ⚠️ CRITICAL: Must-Have Requirements

#### 1. CLI Display

All chat interactions must be displayable as **plain text on CLI** for real-time checking.

Example output format:

```
─────────────────────────────────────────────────────────────────
[Q: A1_001] Model: claude-sonnet-4.5 | Condition: C2 | Turn: 1
─────────────────────────────────────────────────────────────────
>> USER:
Question: Which root category does 'jasmine' belong to?
Options: (A) fruity (B) floral (C) sweet (D) spicy
...

<< ASSISTANT:
I'll validate the descriptors first.
[TOOL CALL] validate_descriptors(["jasmine", "fruity", "floral", "sweet", "spicy"])

>> TOOL RESULT:
{"valid": ["jasmine", "fruity", "floral", "sweet", "spicy"], "invalid": []}

<< ASSISTANT:
[TOOL CALL] get_parent("jasmine")

>> TOOL RESULT:
["floral"]

<< ASSISTANT:
Jasmine's parent is floral, so it belongs to the floral root category.
Therefore, I select (B).

─────────────────────────────────────────────────────────────────
[RESULT] Answer: B | Correct: B | ✓ | Tokens: 650 | Time: 2.3s
─────────────────────────────────────────────────────────────────
```

#### 2. Data Analyzability

| Principle | Description |
|-----------|-------------|
| **Flat structure** | Avoid deeply nested JSON where possible |
| **Consistent keys** | Same field names across all records |
| **Parseable text** | Tool calls, answers extractable via simple regex/parsing |
| **Timestamps** | ISO format for all time fields |
| **Enumerated values** | Consistent strings for status, phase, error types |

#### 3. Testing

- [ ] **Unit tests** for each module
- [ ] **Integration tests** for full evaluation loop
- [ ] **Test with local model** (ollama) before using OpenRouter API
- [ ] **Pilot test** with small question subset before full run

#### 4. Documentation

- [ ] **Docstrings** for all functions and classes
- [ ] **README** for each module explaining purpose and usage
- [ ] **Example usage** in docs or comments
- [ ] **Config documentation** explaining all options

### Implementation Checklist

Before starting implementation, ensure:

- [ ] Logger supports both file output AND CLI display
- [ ] CLI output is human-readable plain text (not raw JSON)
- [ ] All data files use consistent field names
- [ ] Turn logs are line-by-line (JSONL) for easy streaming/parsing
- [ ] Summary CSV is flat (one row per question, easy for pandas)
- [ ] Cache files are resumable (can skip completed questions)
- [ ] All code has tests
- [ ] All code has documentation

---

## 12. Budget Estimate

```
Total runs: 275 questions × 4 conditions × 11 models = 12,100 runs
Est. tokens/run: ~800 average
Total tokens: ~9.7M

Cost breakdown:
- Closed-source: ~$15-25
- Open-source: ~$9-19  
- Judge (F-category, Claude Opus 4.5): ~$5-8

Total: ~$35-55
```

---

## 13. Testing Strategy

| Phase | Description |
|-------|-------------|
| **Phase 1** | Local small model (ollama) to test code |
| **Phase 2** | Pilot: 10 questions × 3 models × 2 conditions via OpenRouter |
| **Phase 3** | Full run: 275 questions × 11 models × 4 conditions |

### Statistical Analysis

- McNemar's test for pairwise condition comparison
- Bonferroni correction for multiple comparisons
- Report: accuracy per task type, per condition, per model
- Secondary metrics: reasoning calls, validation calls, tool usage patterns

---

## 14. Placeholder Items

These items have draft values but should be verified before running experiments:

| Item | Current Value | Notes |
|------|---------------|-------|
| Temperature | 0 | For determinism |
| Max output tokens | 1024 | Enough for reasoning + answer |
| Timeout | 60s | Per API call |
| Retry count | 3 | For all error types |
| Backoff | 2s, 4s, 8s | Exponential |
| Prompt templates | Draft ready | Fine-tune wording before run |
| F-category rubric | Draft ready | Refine criteria before run |
| F-category count | 10-15 | Decide exact number |
| Random seed | 42 | For reproducibility |
| OpenRouter model IDs | Listed above | Verify availability before run |

---

## Appendix: Module Structure

```
src/
├── data/
│   ├── dag.py                    # Load & query graph
│   └── generate_questions.py     # Question generators
│
├── eval/
│   ├── client.py                 # OpenRouter API client
│   ├── tools.py                  # Tool definitions
│   ├── executor.py               # Execute tools against graph
│   ├── evaluator.py              # Single-tool-per-turn loop
│   ├── answer_parser.py          # Extract answers
│   └── scorer.py                 # Correctness checking
│
├── judge/
│   └── llm_judge.py              # LLM-as-judge for F category
│
├── utils/
│   ├── logger.py                 # Logging utilities
│   └── file_io.py                # File read/write helpers
│
└── runner.py                     # Main benchmark runner

configs/
├── models.yaml                   # Model configurations
├── conditions.yaml               # C0-C3 definitions
└── experiment.yaml               # Full experiment config

scripts/
├── run_benchmark.py              # Main entry point
├── run_pilot.py                  # Small-scale test
└── analyze.py                    # Generate all analysis
```

---

*Document Version: 1.0*  
*Created: 2026-01-30*  
*Based on: FlavorGraphTraverser_Plan.md + Discussion Sessions*
