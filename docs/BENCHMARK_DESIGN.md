# Benchmark Design

## Research Goal

Characterize when and how access to a structured domain knowledge base (the SCAA Coffee Flavor Wheel) helps or interferes with LLM reasoning on real-world flavor questions.

The central question is not whether tools improve accuracy in the abstract, but **where the formal standard is sufficient to resolve ambiguity, and where it is not**. Real-world flavor descriptors — the language people actually use — often do not appear verbatim in official taxonomies. A professional may say "plums honey," "winey cherry," or "sweet chili" rather than any registered wheel node. The benchmark is designed around this gap: questions are generated from a richer descriptor vocabulary (1,175-node system graph) than the tool provides (111-node wheel), so the LLM must reason under the same ambiguity a practitioner faces.

The tool limit (5 `get_parent`/`get_children` calls) is intentional: it reflects realistic database query budgets, and more information does not always lead to better decisions — partial matches from an incomplete knowledge base can anchor the model away from correct reasoning. The design tests whether constrained, structured KB access is net-positive under real-world ambiguity conditions.

## Graph Setup

The benchmark uses two separate graphs with an **asymmetric design**:

| | System Graph | Tool Graph (coffee_flavor_wheel) |
|---|---|---|
| **Purpose** | Generate questions | Provided to LLM as a tool |
| **Scale** | 1,175 nodes, 1,824 edges | 111 nodes, 110 edges |
| **Availability** | Internal only | Public |

Questions are generated from the larger System Graph. LLMs are given tool access only to the smaller Tool Graph. This creates a realistic scenario where tool knowledge is incomplete — the LLM must reason and infer, not just look up answers.

## Experimental Conditions

| Condition | Tools | Max Reasoning Calls | Description |
|---|---|---|---|
| **no_tool** | ✗ | — | Baseline (no tool access) |
| **tool** | ✓ | 5 | Tool-augmented |

Key comparison:
- **tool vs no_tool**: Does tool access improve hierarchical reasoning?

### Design Rationale

The benchmark uses a **single-axis design**: with vs. without tools. Earlier designs included a CoT axis (C1: CoT-only, C3: CoT + tools), but this was dropped for two reasons:

1. **Reasoning models** (o1, o3, DeepSeek R1, QwQ) perform chain-of-thought internally — adding a CoT prompt is redundant.
2. **Non-reasoning models** (Llama, Mistral, GPT-4o) should not receive CoT prompts that reasoning models don't need — this would confound the tool-access comparison across model types.

By keeping `no_tool` and `tool` only, the same conditions apply to all models regardless of whether they reason internally, enabling fair cross-model comparison. Models are tested with their **default settings** (reasoning models reason, non-reasoning models don't). The two model types are reported as **separate tracks** in analysis:

- **Track 1 (Non-reasoning):** Llama, Mistral, GPT-4o, etc.
- **Track 2 (Reasoning):** o1/o3, DeepSeek R1, QwQ, gpt-oss, etc.

This halves the evaluation count (550 instead of 1100 per model) while preserving the core research question.

### System Prompt Design

System prompts follow MMLU/τ-bench conventions — neutral framing without expert role claims:
- **no_tool**: `"The following is a question about the coffee flavor wheel hierarchy."` (MMLU-style subject context)
- **tool**: Adds `"You have access to a coffee flavor graph database via the provided tools. You may use the tools to look up relationships, or answer directly — your choice."` (τ-bench-style capability description, opt-in rather than instructed)

This design isolates the tool contribution: the model is never told it's an "expert," so `tool` vs `no_tool` differences reflect tool access, not prompting authority. The tool call budget is dynamically injected into the system prompt (see `prompts/tool_budget.txt`).

All prompts are externalized to `prompts/*.txt` files for reproducibility. See `configs/conditions.yaml` for the full condition definitions.

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

**Target count:** 15 (G1: 5, G2: 5, G3: 5)
**Judge panel:** Claude Opus 4.6, Gemini 3.1 Pro, GPT-5.4 Pro (optional) — multi-judge scoring

## Tool Interface

LLMs query the Tool Graph via function calling. Three tools are exposed:

| Tool | Purpose | Cost | Limit |
|---|---|---|---|
| `validate_descriptors` | Check if descriptors exist in graph | **Free** | No call limit, max 10 items/call |
| `get_parent` | Get parent node(s) of a descriptor | **Counted** | Shared 5-call budget |
| `get_children` | Get child node(s) of a descriptor | **Counted** | Shared 5-call budget |

Tool descriptions explicitly state:
- `validate_descriptors`: "No call limit — use freely. Validation is optional: you can call get_parent or get_children directly without validating first."
- `get_parent`/`get_children`: "Counts toward your reasoning call budget (shared)."

This prevents the validate-then-give-up anti-pattern observed in early testing, where models would validate question descriptors (which are excluded from the tool graph), get `invalid`, and stop. Tool descriptions are defined in `FlavorGraphTraverser/evaluation/tools/definitions.py`.

**Fairness principle:** Validation reveals only existence, not relationships. Name matching is separated from reasoning ability.

**ICL mode:** Models without native function calling (DeepSeek, Llama-4 Maverick, Nemotron) use text-based tool simulation. Tool instructions and a traversal example are injected into the system prompt (see `prompts/icl_tools.txt`).

## Turn Structure (tool condition)

The model can call tools freely within its budget. `validate_descriptors` calls are unlimited; `get_parent`/`get_children` share a 5-call budget.

```
Turns 1–N: Tool Loop
  - LLM receives question + tool definitions + budget note
  - Can call validate_descriptors (no limit)
  - Can call get_parent/get_children (counts toward 5-call budget)
  - Can answer directly at any turn

Forced Answer: After 5 Reasoning Calls OR Model Gives Up
  Stage 1 — Emphatic message with full context:
    "You have used your tool call budget (5 reasoning calls).
     No more tool calls are allowed. Based on the information
     gathered above, you MUST provide your final answer now."
    Sent with tool_choice="none" so model can synthesise tool findings.

  Stage 2 — Fallback (if Stage 1 returns empty):
    Context surgery: strip all tool history, send clean
    [system, original question, "Provide your final answer now."]
    This handles models that get stuck in tool-calling mode.
```

Answer format instructions use imperative framing (`"You MUST end your response with exactly this format"`) to ensure format compliance without relying on expert role prompting. See `prompts/answer_format_*.txt`.

## Answer Extraction

Answers are extracted using a **three-layer pipeline** (see `answer_parser.py`):

| Layer | Scope | Confidence |
|-------|-------|-----------|
| **Layer 1: Canonical** | `"I select (X)"`, `"answer is (X)"` on visible content | High |
| **Layer 2: Normalization** | Model-specific text transforms (bold markdown, truncated parens), then re-run Layer 1; try `thinking_content` for reasoning models | High |
| **Layer 3: Fallback** | Last 3 sentences only, gated by signal words ("select", "answer", "therefore") | Low (tagged `[low-confidence]`) |

Multi-select questions (A1, A4, A5) have no fallback layer — parse failure yields `parse_error` rather than a risky guess.

The parser accepts optional `thinking_content` (for reasoning models like kimi-k2.5 whose visible output may be truncated) and `model_id` (for model-specific normalization rules).

## Scoring

Each question produces a continuous **0–1 score**:

| Question type | Scoring | Example |
|---|---|---|
| **Single-choice** (A2, A3, E1, E2, E3) | Binary: 0 or 1 | Correct = 1, wrong = 0 |
| **Multi-select** (A1, A4, A5) | F1 between predicted and correct sets | Correct={B,C,D}, model={B,C} → F1=0.80 |
| **F-category** (open-ended) | judge_score / 5 | Judge gives 4 → score = 0.80 |

Two aggregate scores:

- **Macro score** (primary): Mean of per-category averages. Each of the 9 categories (A1–A5, E1–E3, F) contributes equally regardless of question count — F's 15 questions carry the same weight as A1's 50.
- **Micro score**: Mean of all individual question scores. Favors categories with more questions.
- **Accuracy** (binary): Fraction of exactly correct answers. Reported for comparison but not the primary metric.

Scoring is implemented in `FlavorGraphTraverser/evaluation/utils/answer_parser.py:compute_question_score()`.

### LLM-as-a-Judge (F-category)

F-category questions are scored by a **multi-judge panel** on a 0–5 rubric. Each judge receives:
1. The original question text
2. The model's response
3. A per-question rubric and evaluation criteria (from question metadata)
4. Closing instruction: "Evaluate the response above and provide your score. End with: Score: N"

**Judge panel** (none are in the tested model set, avoiding self-judging bias):

| Judge | Model | Provider |
|-------|-------|----------|
| Judge 1 | Claude Opus 4.6 | Anthropic |
| Judge 2 | Gemini 3.1 Pro | Google |
| Judge 3 | GPT-5.4 Pro | OpenAI (optional) |

Using multiple judges from different providers enables **inter-judge agreement** reporting (Cohen's kappa / Krippendorff's alpha) and eliminates single-model bias. The final F-category score is the mean across judges.

**Workflow**: Run evaluation once with `--no-judge`, then score F-category responses with each judge model separately. This avoids re-running evaluations and allows judge comparison on identical model outputs.

```bash
# Step 1: Run evaluation (no judging)
python scripts/experiment/run_experiment.py --conditions no_tool tool --models ... --no-judge

# Step 2: Score with each judge
python scripts/experiment/run_experiment.py --conditions no_tool tool --models ... --judge-model anthropic/claude-opus-4.6
python scripts/experiment/run_experiment.py --conditions no_tool tool --models ... --judge-model google/gemini-3.1-pro-preview
```

Judge prompts are in `prompts/judge_system.txt` and `prompts/judge_closing.txt`. A mean score ≥ 3 counts as `is_correct=True` for binary accuracy reporting.

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
| F  | 15 | 15 | Open-ended (LLM-judged, 0–5 scoring) |
| **Total** | **275** | **275** | |

## Models

**11 models total (4 closed-source, 7 open-source)**

| Provider | Model | OpenRouter ID | Reasoning | Tool Mode |
|---|---|---|---|---|
| Anthropic | Claude Sonnet 4.6 | `anthropic/claude-sonnet-4.6` | Yes | Native |
| OpenAI | GPT-5.4 | `openai/gpt-5.4` | Yes | Native |
| Google | Gemini 3 Flash | `google/gemini-3-flash-preview` | Yes | Native |
| xAI | Grok 4.1 Fast | `x-ai/grok-4.1-fast` | Yes | Native |
| OpenAI | GPT-OSS 120B | `openai/gpt-oss-120b` | Yes | Native |
| Alibaba | Qwen3.5 397B | `qwen/qwen3.5-397b-a17b` | Yes | Native |
| Moonshot | Kimi K2.5 | `moonshotai/kimi-k2.5` | Yes | Native |
| Meta | Llama 4 Maverick | `meta-llama/llama-4-maverick` | No | ICL |
| DeepSeek | DeepSeek V3.2 | `deepseek/deepseek-v3.2` | Yes | Native |
| Mistral | Mistral Medium 3.1 | `mistralai/mistral-medium-3.1` | No | Native |
| NVIDIA | Nemotron 3 Super 120B | `nvidia/nemotron-3-super-120b-a12b` | Yes | ICL |

**Judge panel** (multi-judge, none overlap with tested models):
- Claude Opus 4.6 (`anthropic/claude-opus-4.6`)
- Gemini 3.1 Pro (`google/gemini-3.1-pro-preview`)
- GPT-5.4 Pro (`openai/gpt-5.4-pro`) — optional, high cost

See `docs/COST.md` for detailed budget breakdown.

## Metrics

For each evaluated question, recorded fields include:

```json
{
  "question_id": "A1_001",
  "model": "anthropic/claude-sonnet-4.6",
  "condition": "tool",
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
[Q: A1_001] Model: claude-sonnet-4.6 | Condition: tool | Turn: 1
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

## Results Summary

The experiment was completed on April 13–16, 2026: 6,050 evaluations (11 models × 2 conditions × 275 questions), with a 3-judge panel (Opus 4.6, Gemini 3.1 Pro, GPT-5.4 Pro) for F-category scoring.

**Key finding:** All 11 models showed **negative tool Δ** — tool access degraded performance across the board (macro score Δ from -0.02 to -0.14). This was consistent across model types and question categories.

| Model | no_tool | tool | Δ |
|-------|---------|------|---|
| gemini-3-flash | 0.648 | 0.596 | -0.052 |
| kimi-k2.5 | 0.624 | 0.570 | -0.053 |
| claude-sonnet-4.6 | 0.636 | 0.549 | -0.087 |
| gpt-5.4 | 0.630 | 0.526 | -0.105 |
| mistral-medium-3.1 | 0.598 | 0.456 | -0.142 |

**What this means:**

- **Partial KB coverage creates anchoring harm**, not just neutral absence. When the 111-node tool graph returns "invalid" for real-world descriptors (which are in the 1,175-node system graph), models treat this as negative evidence and abandon correct knowledge-based reasoning.
- **The tool-skip problem is unsolvable by prompting alone.** Despite the system prompt saying "a descriptor absent from the graph may still relate to SCAA categories you already know," models consistently anchor on tool output over their own knowledge.
- **The boundary is sharper than hypothesized.** The original design expected positive tool benefit on taxonomy tasks (A1–A3) and negative on similarity tasks (E). In practice, even taxonomy tasks showed negative Δ for most models, because question descriptors are intentionally drawn from outside the tool graph's 111-node vocabulary.

## Completed Budget

```
Total evaluations: 275 questions × 2 conditions × 11 models = 6,050
Judge calls: 15 F-questions × 2 conditions × 11 models × 3 judges = 990

Evaluation cost:  ~$50  (24M tokens)
Judge cost:       ~$9   (2 judges: Opus + Gemini) + ~$45 (GPT-5.4 Pro optional)
Re-runs:          ~$5   (kimi payment errors, empty responses, nemotron token limit)

Total spent: ~$60 (2-judge panel) or ~$105 (3-judge panel)
```

See `docs/COST.md` for detailed per-model breakdown.
