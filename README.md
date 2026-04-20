# FlavorGraphTraverser

> Benchmarking Tool-Augmented LLM Inference on Coffee Flavor Hierarchy Reasoning

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Python library for representing and traversing coffee flavor hierarchies as directed acyclic graphs (DAGs). This package enables benchmarking of LLM inference on hierarchical reasoning tasks using the coffee flavor wheel taxonomy.

---

## Research Overview

### Research Question

For domain-specific hierarchical reasoning, how does tool-augmented inference compare to direct prompting?

### Thesis

Structured KB access (the SCAA Coffee Flavor Wheel) provides reliable benefit for taxonomy-grounded queries but offers no benefit — or introduces anchoring harm — for semantic similarity and complex path reasoning tasks where real-world descriptor ambiguity exceeds what the hierarchy encodes.

### Key Finding

All 11 models scored **lower** with tool access than without (macro score Δ ranges from -0.02 to -0.14). Tool-augmented reasoning consistently anchors models on incomplete graph data, degrading performance across question types.

See [docs/BENCHMARK_DESIGN.md](docs/BENCHMARK_DESIGN.md) for the full experimental design, and [docs/RESEARCH_POSITION.md](docs/RESEARCH_POSITION.md) for the design philosophy.

---

## Quick Start

### 1. Basic Graph Operations

```python
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph

data = load_graph_data('data/graphs/coffee_flavor_wheel.pkl')
graph = CoffeeDescriptionGraph(
    data['descriptions'],
    data['connections'],
    root=data['root']
)

print(graph.children_of_description('berry'))
# ['strawberry', 'blueberry', 'blackberry', 'raspberry']

paths = graph.pathways_between_descriptions('ROOT:SYSTEM', 'rose')
```

### 2. Use Graph Tools with LLMs

```python
from FlavorGraphTraverser.evaluation.client import create_client, Message
from FlavorGraphTraverser.evaluation.tools import GraphToolExecutor, get_tool_definitions

executor = GraphToolExecutor(graph)

# Validate descriptors (FREE — not counted toward tool limit)
result = executor.validate_descriptors(['rose', 'chocolate', 'unknown'])
# {'valid': ['rose', 'chocolate'], 'invalid': ['unknown']}

# Get parent (COUNTED — toward 5-call budget)
result = executor.get_parent('blueberry')
# {'descriptor': 'blueberry', 'parents': ['berry'], 'error': None}
```

### 3. Run a Benchmark Evaluation

```python
from FlavorGraphTraverser.evaluation import create_client, GraphToolExecutor, QuestionEvaluator

client = create_client("openrouter", "anthropic/claude-sonnet-4.6")
evaluator = QuestionEvaluator(client, executor, "tool")
result = evaluator.evaluate(question)

print(f"Score: {result.score:.2f}, Correct: {result.is_correct}, Reasoning calls: {result.metrics.reasoning_calls}")
```

### 4. Run Tests

```bash
pytest
./scripts/run_tests.sh quick      # no Ollama required
./scripts/run_tests.sh coverage
```

---

## Installation

### From Source

```bash
git clone https://github.com/b05611038/flavor_graph_traverser.git
cd flavor_graph_traverser
pip install -r requirements.txt
pip install -e .
```

### Environment Setup

```bash
cp .env.example .env
# Add OPENROUTER_API_KEY=sk-or-v1-...
```

### Dependencies

- `numpy>=1.19.0`
- `python-igraph>=0.10.0`
- `requests>=2.25.0`
- `pyyaml>=5.4.0`

---

## Architecture

```
FlavorGraphTraverser/
├── graph.py                    # CoffeeDescriptionGraph — DAG representation
├── utils.py                    # Type validation utilities
├── constants.py                # Default connection weights
├── flavor_categories.py        # Reference flavor hierarchy (9 categories)
├── loader.py                   # Graph loading utilities
│
├── evaluation/                 # Benchmarking infrastructure
│   ├── client/                 # LLM clients (OpenRouter for production; Ollama, vLLM for local testing)
│   ├── tools/                  # Graph tool interface (function calling)
│   ├── utils/                  # Answer parser, config loader, scoring
│   ├── judge/                  # LLM-as-a-judge for F-category scoring
│   ├── evaluator.py            # QuestionEvaluator — single-question loop
│   └── batch_runner.py         # BatchRunner — multi-question/model/condition
│
└── generation/                 # Question generation
    ├── question_generator.py   # QuestionGenerator orchestrator
    ├── samplers.py             # Descriptor sampling strategies
    └── validators.py           # Question validation (incl. leakage checks)

prompts/                        # All prompt templates (plain text files)
├── __init__.py                 # load_prompt("name", key=val) loader
├── judge_system.txt            # LLM-as-a-judge system prompt
├── judge_closing.txt           # Judge evaluation closing instruction
├── answer_format_single.txt    # Single-choice: "Therefore, I select (X)"
├── answer_format_multi.txt     # Multi-select: "Therefore, I select (X, Y, ...)"
├── answer_format_open.txt      # F-category open-ended instruction
├── forced_answer.txt           # Emphatic "budget reached" message
├── forced_answer_fallback.txt  # Context surgery fallback
├── tool_budget.txt             # Tool call budget injection
└── icl_tools.txt               # ICL tool instructions + example traversal

configs/                        # YAML configuration files
├── models.yaml                 # 11 models + judge
├── conditions.yaml             # no_tool / tool conditions
├── experiment.yaml             # Experiment configuration
└── README.md                   # Configuration guide

data/                           # Data files (private, excluded from git)
├── graphs/                     # Graph .pkl files
├── filtering/                  # Filtered nodes + exception lists
└── questions/                  # Generated benchmark questions

scripts/                        # Executable scripts
├── experiment/
│   ├── run_experiment.py       # Main experiment runner
│   └── test_full_workflow.py   # End-to-end pipeline test
├── generation/
│   ├── generate_all_questions.py    # Generate all question types
│   ├── generate_a4_multiselect.py   # A4 multi-select generator
│   ├── generate_a5_multiselect.py   # A5 multi-select generator
│   └── generate_test_questions.py   # Quick test question generator
├── audit/
│   ├── question_auditor_unified.py  # Web-based auditor + results viewer
│   ├── inspect_questions.py         # Quality inspection
│   ├── manage_queue.py              # Audit queue management
│   ├── review_flagged.py            # CLI flagged question review
│   └── manage_audit_state.py        # Audit state utilities
├── data/
│   ├── backup_manager.py            # Question backup/restore
│   ├── add_questions_live.py        # Add questions to running auditor
│   ├── queue_live.py                # Live queue management client
│   ├── export_benchmark_questions.py# Export confirmed questions
│   ├── pack_system_graph.py         # Build system graph
│   ├── flavor_filter.py             # Hierarchical flavor filtering
│   └── clean_orphaned_audit_entries.py
└── run_tests.sh                # Test runner

tests/                          # Test suite
├── client/                     # Client layer tests
├── tools/                      # Tool interface tests
└── integration/                # Integration tests
```

---

## Question Generation

Generate questions from the System Graph:

```bash
# Generate all task types
python scripts/generation/generate_all_questions.py

# Generate specific task type(s)
python scripts/generation/generate_all_questions.py E3
python scripts/generation/generate_all_questions.py E2 E3 --count 200
```

See [docs/QUESTION_GENERATION.md](docs/QUESTION_GENERATION.md) for the full generation pipeline, data leakage prevention, and validation details.

---

## Question Auditing

Review generated questions via web interface:

```bash
bash scripts/start_auditor.sh
# Opens at http://localhost:5000
```

See [docs/AUDITING.md](docs/AUDITING.md) for the audit workflow, queue management, and backup system.

---

## Experimental Setup

### Conditions

| Condition | Tools | Max Reasoning Calls | Description |
|-----------|-------|---------------------|-------------|
| **no_tool** | ✗ | — | Baseline (no tool access) |
| **tool** | ✓ | 5 | Tool-augmented |

Single-axis design: **with vs. without tools**. CoT conditions (C1, C3) were dropped because reasoning models already think internally (making CoT redundant), and adding CoT only for non-reasoning models would confound cross-model comparison. All models are tested with default settings; reasoning vs non-reasoning is an analysis dimension, not a controlled variable.

System prompts follow MMLU/τ-bench conventions: neutral framing (`"The following is a question about the coffee flavor wheel hierarchy."`) without expert role claims. Tool access is described as opt-in (`"You may use the tools... your choice."`). See `configs/conditions.yaml` for full prompts.

### Tool Interface

Three tools exposed to LLMs:

1. **`validate_descriptors`** (no call limit) — check if descriptors exist in graph
2. **`get_parent`** (counts toward budget, max 5 shared) — get parent node(s) of a descriptor
3. **`get_children`** (counts toward budget, max 5 shared) — get child node(s) of a descriptor

The tool call budget is injected dynamically into the system prompt. When the budget is exhausted, an emphatic forced-answer message is sent; if the model still returns empty, a context-surgery fallback strips tool history and queries with a clean prompt.

### Scoring

Each question scores **0–1** continuously:

| Question type | Scoring method |
|---|---|
| Single-choice (A2, A3, E1, E2, E3) | Binary: 0 or 1 |
| Multi-select (A1, A4, A5) | F1 between predicted and correct sets |
| F-category (open-ended) | judge_score / 5 (LLM-as-a-judge, 0–5 scale) |

Two aggregate scores are reported:
- **Macro score**: mean of per-category averages (each of 9 categories weighted equally)
- **Micro score**: mean of all individual question scores

### Prompt Management

All prompt templates are externalized to `prompts/*.txt` files. To modify any prompt, edit the `.txt` file directly — no Python changes needed.

```python
from prompts import load_prompt

# Simple load
system = load_prompt("judge_system")

# With placeholder substitution
fmt = load_prompt("answer_format_single", options_list="A, B, C, or D")
budget = load_prompt("tool_budget", max_calls=5)
```

### Question Dataset (~275 questions)

| Category | Task | Count | Status |
|---|---|---|---|
| **A** Taxonomic | A1 Root Classification | 50 | Confirmed |
| | A2 Ancestor Verification | 50 | Confirmed |
| | A3 Sibling Identification | 30 | Confirmed |
| | A4 Path Reconstruction | 30 | Confirmed |
| | A5 Lowest Common Ancestor | 20 | Confirmed |
| **E** Similarity | E1 Similarity Ranking | 30 | Confirmed |
| | E2 Pairwise Comparison | 30 | Confirmed |
| | E3 Odd One Out | 20 | Confirmed |
| **F** Open | F Open Reasoning | 15 | Confirmed |

---

## Testing

```bash
# Run all tests
pytest

# Quick tests (no Ollama required)
./scripts/run_tests.sh quick

# With coverage
./scripts/run_tests.sh coverage
```

See [docs/TESTING.md](docs/TESTING.md) for complete test documentation.

---

## Documentation

| Document | Contents |
|---|---|
| [docs/BENCHMARK_DESIGN.md](docs/BENCHMARK_DESIGN.md) | Experimental design, conditions, scoring, tool interface |
| [docs/QUESTION_GENERATION.md](docs/QUESTION_GENERATION.md) | Generation pipeline, leakage prevention, validation |
| [docs/AUDITING.md](docs/AUDITING.md) | Audit workflow, results viewer, queue management |
| [docs/TESTING.md](docs/TESTING.md) | Test suite, fixtures, CI |
| [docs/RESEARCH_POSITION.md](docs/RESEARCH_POSITION.md) | Design philosophy, F-question rationale |
| [docs/COST.md](docs/COST.md) | Completed experiment cost breakdown |
| [docs/RELEASING.md](docs/RELEASING.md) | Release checklist (code, data, HF dataset) |
| [scripts/analysis/README.md](scripts/analysis/README.md) | Analysis module: tables, figures, statistical tests, mechanistic analyses |
| [configs/README.md](configs/README.md) | YAML configuration reference |
| [prompts/](prompts/) | All prompt templates (one `.txt` file per prompt) |

---

## Core API

### CoffeeDescriptionGraph

```python
graph.children_of_description(desc)     # Get direct descendants
graph.parents_of_description(desc)      # Get direct ancestors
graph.pathways_between_descriptions(from, to, k=1)  # K shortest paths
graph.distance_between_descriptions(from, to)       # Shortest distance
graph.valid_construction()              # Verify DAG property
graph.adjacency_matrix()               # Get matrix representation
graph.plot(filename)                   # Save graph visualization
```

---

## Outputs

1. **Table 1**: Macro score (%) by Model × Condition (no_tool, tool), grouped by model type
2. **Table 2**: Per-category score breakdown (A1–A5, E1–E3, F) — with F1 for multi-select and judge scores for F
3. **Figure 1**: Tool benefit (Δ score) by task type — showing where KB access helps vs. anchors
4. **Figure 2**: Tool call count vs. accuracy — diminishing or negative returns
5. **Statistical analysis**: Paired significance tests on no_tool vs. tool per-question scores
6. **Dashboard**: Interactive results viewer with CSV export (`http://localhost:5000/results`)

---

## License

MIT License — see [LICENSE](LICENSE) file for details.

---

## Citation

```bibtex
@software{flavor_graph_traverser_2026,
  title = {FlavorGraphTraverser: Benchmarking Tool-Augmented LLM Inference on Hierarchical Reasoning},
  author = {Zhang, Yutang},
  year = {2026},
  url = {https://github.com/b05611038/flavor_graph_traverser}
}
```

---

## Acknowledgments

Part of the IR-BERT Coffee Chat System project.

**Related Work:**
- Coffee flavor wheel taxonomy (Specialty Coffee Association)
- Tool-augmented LLM research
- Hierarchical reasoning benchmarks
