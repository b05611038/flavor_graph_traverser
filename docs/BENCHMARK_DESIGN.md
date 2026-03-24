# Benchmark Design

## Research Goal

Benchmark tool-augmented LLM inference on coffee flavor hierarchy reasoning. The central question: for domain-specific hierarchical tasks, does giving LLMs a graph traversal tool achieve near-full-context accuracy at lower token cost?

## Graph Setup

The benchmark uses two separate graphs with an **asymmetric design**:

| | System Graph | Tool Graph (coffee_flavor_wheel) |
|---|---|---|
| **Purpose** | Generate questions | Provided to LLM as a tool |
| **Scale** | 1,175 nodes, 1,824 edges | 111 nodes, 110 edges |
| **Availability** | Internal only | Public |

Questions are generated from the larger System Graph. LLMs are given tool access only to the smaller Tool Graph. This creates a realistic scenario where tool knowledge is incomplete — the LLM must reason and infer, not just look up answers.

## Experimental Conditions

| Condition | Tools | CoT | Max Reasoning Calls | Description |
|---|---|---|---|---|
| **C0** | ✗ | ✗ | — | Zero-shot baseline |
| **C1** | ✗ | ✓ | — | CoT with structural hint |
| **C2** | ✓ | ✗ | 3 | Tools only |
| **C3** | ✓ | ✓ | 3 | CoT + Tools (full) |

Key comparisons:
- **C2 vs C0**: Benefit of tool access
- **C1 vs C0**: Benefit of structured reasoning alone
- **C3 vs C2**: Does CoT improve tool-augmented reasoning?

**CoT structural hint** (used in C1, C3):
```
Flavor descriptors are organized in a hierarchical graph structure
(e.g., 'strawberry' → 'berry' → 'fruity'). Let's think step-by-step.
```

## Task Types

### Category A: Taxonomic Reasoning

| Task | Format | Tests |
|---|---|---|
| **A1** Root Classification | Multi-select: which root categories does descriptor belong to? | DAG-aware multi-path root lookup |
| **A2** Ancestor Verification | Yes/No: is X an ancestor of Y? | Ancestor relationship reasoning |
| **A3** Sibling Identification | 4-choice: which shares the same parent as X? | Parent-child traversal |
| **A4** Path Reconstruction | Multi-select: which of these paths from root to X are fully correct? | Full hierarchy tracing |
| **A5** LCA Finding | 4-choice: what is the lowest common ancestor of X and Y? | Common ancestor reasoning |

**Target counts:** A1: 50, A2: 50, A3: 30, A4: 30, A5: 20

### Category E: Similarity Reasoning

| Task | Format | Tests |
|---|---|---|
| **E1** Similarity Ranking | 4-choice: rank [A, B, C] by similarity to target | Graph distance ordering |
| **E2** Pairwise Comparison | **3-choice**: which of A, B, or C is most similar to target? | Relative graph distance (random baseline 33%) |
| **E3** Odd One Out | 4-choice: which does not belong with the others? | Cluster membership detection |

**E2 constraints:**
- All 3 options at strictly increasing graph distances from target
- `min_closer_distance=2`: closest option must be at least distance 2 (prevents trivial parent/name matches)
- Options must not share words with target (prevents name-matching shortcut)
- All candidates must share the same root category as the target

**E3 constraints:**
- 3 siblings share the same direct parent; 1 odd-one from a different root category
- No word shared across all 3 siblings (prevents trivial pattern detection)
- No near-duplicate sibling names (normalized prefix check)
- Odd-one must not share words with any sibling

**All E1/E2 candidates must share the same root category as the target** (avoids ambiguous cross-branch distances through ROOT:SYSTEM at weight=10).

**Target counts:** E1: 30, E2: 30, E3: 20

### Category F: Open Reasoning (Professional Scenarios)

LLM-judged open-ended questions requiring branch-level flavor hierarchy reasoning in realistic professional contexts. No single correct answer — scoring evaluates reasoning quality (0-5 scale).

**Three scenario groups (5 questions each):**

| Group | Context | Reasoning tested |
|---|---|---|
| **G1** Communication | Barista-customer interactions | Translate informal language ↔ hierarchy vocabulary |
| **G2** Professional Decision-Making | Sourcing, blending, menu design | Branch reasoning for business decisions with practical constraints |
| **G3** Production Factors | Roasting, fermentation, processing | Connect production variables to flavor hierarchy positions |

**Key design principles:**
- Buyer/owner language is indirect — requires branch mapping to interpret (no word matching)
- Reference tables describe physical processes, not flavor outcomes
- Multiple valid answers accepted if supported by branch reasoning
- Scoring rubrics evaluate reasoning quality, not specific conclusions

**Target count:** 16 (G1: 5, G2: 5, G3: 6 including 1 abandoned draft)
**Judge model:** Claude Opus 4.5 (with system graph tool access)

## Tool Interface

LLMs query the Tool Graph via function calling. Three tools are exposed:

| Tool | Purpose | Cost | Limit |
|---|---|---|---|
| `validate_descriptors` | Check if descriptors exist in graph | **Free** | Unlimited, max 10 items/call |
| `get_parent` | Get parent node(s) of a descriptor | **Counted** | Shared 3-call limit |
| `get_children` | Get child node(s) of a descriptor | **Counted** | Shared 3-call limit |

**Fairness principle:** Validation reveals only existence, not relationships. Name matching is separated from reasoning ability.

## Turn Structure (C2, C3)

```
Turn 1: Initial Query
  - LLM receives question + tool definitions
  - Can call validate_descriptors (FREE)
  - Can call get_parent/get_children (#1)
  - Can answer directly

Turn 2: After Tool Result
  - LLM sees question + full history
  - Can call validate_descriptors (FREE)
  - Can call get_parent/get_children (#2)
  - Can answer directly

Turn 3: After 2nd Tool Result
  - Same as Turn 2
  - Can call get_parent/get_children (#3)

Forced Answer: After 3 Reasoning Calls
  - System: "Provide your final answer now"
  - LLM MUST answer (no more tool calls)
```

Answer can come at any turn; forced after 3 reasoning calls.

## Answer Extraction

Answers extracted using priority patterns:

```python
patterns = [
    r"I select \(([A-D])\)",           # Primary
    r"answer is \(([A-D])\)",          # Fallback 1
    r"\(([A-D])\)",                    # Last standalone (X)
    r"\b([A-D])\b(?!.*\b[A-D]\b)",    # Last standalone letter
]
# None found → parse_error → marked as incorrect
```

## Question Set Status

| Task | Target | Confirmed | Format |
|---|---|---|---|
| A1 | 50 | 50 | Multi-select (0–N correct roots) |
| A2 | 50 | 50 | Yes/No |
| A3 | 30 | 30 | 4-choice single answer |
| A4 | 30 | 30 | Multi-select paths (0–5 correct) |
| A5 | 20 | 20 | 4-choice single answer |
| E1 | 30 | 30 | 4-choice ranking |
| E2 | 30 | 30 | 3-choice single answer |
| E3 | 20 | 20 | 4-choice single answer |
| F  | 16 | 16 | Open-ended (LLM-judged, 0-5 scoring) |
| **Total** | **276** | **276** | |

## Models

**11 models total (4 closed-source, 7 open-source)**

| Provider | Model | OpenRouter ID |
|---|---|---|
| Anthropic | Claude Sonnet 4.5 | `anthropic/claude-sonnet-4.5` |
| OpenAI | GPT-5.2 | `openai/gpt-5.2` |
| Google | Gemini 3 Flash | `google/gemini-3-flash-preview` |
| xAI | Grok 4.1 Fast | `x-ai/grok-4.1-fast` |
| OpenAI | GPT-OSS 120B | `openai/gpt-oss-120b` |
| Alibaba | Qwen3-235B-A22B | `qwen/qwen3-235b-a22b` |
| Moonshot | Kimi K2 | `moonshotai/kimi-k2` |
| Meta | Llama 4 Maverick | `meta-llama/llama-4-maverick` |
| DeepSeek | DeepSeek Chat | `deepseek/deepseek-chat` |
| Mistral | Mistral Medium 3 | `mistralai/mistral-medium-3` |
| NVIDIA | Nemotron Super 49B | `nvidia/llama-3.3-nemotron-super-49b-v1` |

**Judge:** Claude Opus 4.5 (for F-category questions)

## Metrics

For each evaluated question, recorded fields include:

```json
{
  "question_id": "A1_001",
  "model": "anthropic/claude-sonnet-4.5",
  "condition": "C2",
  "result": {
    "model_answer": "B",
    "correct_answer": "B",
    "is_correct": true,
    "status": "success"
  },
  "metrics": {
    "reasoning_calls": 2,
    "validation_calls": 1,
    "total_turns": 3,
    "input_tokens": 850,
    "output_tokens": 120,
    "total_tokens": 970,
    "latency_ms": 2340
  }
}
```

Status values: `success`, `parse_error`, `api_error`, `refusal`, `tool_error`

## Error Handling

| Error Type | Handling |
|---|---|
| API timeout | Retry 3× with exponential backoff (2s, 4s, 8s) |
| Rate limit (429) | Wait `Retry-After`, then retry |
| API error (5xx) | Retry 3× with backoff |
| Invalid tool format | Attempt repair once, else `tool_error` |
| Invalid descriptor | Return error to model, count as reasoning call |
| Model refusal | Mark as `refusal`, count as incorrect |
| Answer extraction fail | Mark as `parse_error`, count as incorrect |

## Result Caching

Completed results are cached to support resuming interrupted runs:

```
results/cache/{model}/{condition}/{question_id}.json
```

## CLI Display Format

Each evaluation turn is displayed as plain text:

```
─────────────────────────────────────────────────────────────────
[Q: A1_001] Model: claude-sonnet-4.5 | Condition: C2 | Turn: 1
─────────────────────────────────────────────────────────────────
>> USER:
Question: Which root category does 'jasmine' belong to?
Options: (A) fruity (B) floral (C) sweet (D) spicy

<< ASSISTANT:
[TOOL CALL] validate_descriptors(["jasmine", "fruity", "floral"])

>> TOOL RESULT:
{"valid": ["jasmine", "fruity", "floral", "sweet", "spicy"], "invalid": []}

<< ASSISTANT:
[TOOL CALL] get_parent("jasmine")

>> TOOL RESULT:
["floral"]

<< ASSISTANT:
Jasmine's parent is floral. Therefore, I select (B).

─────────────────────────────────────────────────────────────────
[RESULT] Answer: B | Correct: B | ✓ | Tokens: 650 | Time: 2.3s
─────────────────────────────────────────────────────────────────
```

## Expected Results

**Table 1:** Accuracy (%) by Model × Condition (C0–C3)
**Table 2:** Per-task accuracy breakdown
**Figure 1:** Accuracy vs. tool call count
**Figure 2:** Token cost vs. accuracy trade-off

**Success criteria:** C3 achieves ≥90% of C0+full-context baseline accuracy with significantly fewer tokens.

## Budget Estimate

```
Total runs: 276 questions × 4 conditions × 11 models = 12,144 runs
Est. tokens/run: ~800 average
Total tokens: ~9.7M

Cost breakdown:
- Closed-source:    ~$15–25
- Open-source:      ~$9–19
- Judge (F-cat.):   ~$5–8

Total: ~$35–55
```
