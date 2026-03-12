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

| Condition | Description |
|---|---|
| **C0** | Zero-shot direct prompting (no tools, no examples) |
| **C1** | Few-shot prompting |
| **C2** | Chain-of-thought prompting |
| **C3** | Tool-augmented, limited calls |
| **C4** | Tool-augmented, unlimited calls |
| **C5** | Full-context baseline (entire System Graph in prompt) |

Key comparisons:
- **C2 vs C0**: Benefit of structured reasoning
- **C3/C4 vs C0**: Benefit of tool access
- **C3/C4 vs C5**: Tool efficiency vs. full context

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

### Category F: Open Reasoning

LLM-judged questions with no single correct answer:
- Describe the flavor profile of descriptor X
- Explain the relationship between X and Y
- Category overview questions

**Target count:** 15

## Tool Interface

LLMs query the Tool Graph via function calling:

```json
{
  "tools": [
    { "name": "get_children",  "description": "Get child nodes of a flavor node" },
    { "name": "get_parent",    "description": "Get parent node of a flavor node" },
    { "name": "find_path",     "description": "Find path between two flavor nodes" },
    { "name": "get_ancestors", "description": "Get all ancestors of a flavor node" }
  ]
}
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
| F  | 15 | 0  | Open-ended (LLM-judged) |
| **Total** | **275** | **260** | |

## Expected Results

**Table 1:** Accuracy (%) by Model × Condition (C0–C5)
**Table 2:** Per-task accuracy breakdown (C0 vs C3 vs C5)
**Figure 1:** Accuracy vs. tool call count
**Figure 2:** Token cost vs. accuracy trade-off

**Success criteria:** C3/C4 achieves ≥90% of C5 accuracy with significantly fewer tokens.
