# FlavorGraphTraverser

> Benchmarking Tool-Augmented LLM Inference on Coffee Flavor Hierarchy Reasoning

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Python library for representing and traversing coffee flavor hierarchies as directed acyclic graphs (DAGs). This package enables benchmarking of LLM inference on hierarchical reasoning tasks using the coffee flavor wheel taxonomy.

---

## Paper

**Chang, Yu-Tang & Chen, Shih-Fang (2026).** Evaluating Tool-augmented Large Language Models on Hierarchical Flavor Reasoning: FlavorReasonBench and Its First Application to Coffee.

> This paper is currently under review. No preprint is available. Citation information will be updated upon publication.

**Data and reproducibility:**
- Benchmark dataset: https://doi.org/10.5281/zenodo.20339333
- Reproducibility data and code: https://doi.org/10.5281/zenodo.20338516

---

## Research Overview

### Research Question

For domain-specific hierarchical reasoning, how does tool-augmented inference compare to direct prompting?

### Key Finding

Tool access **bifurcates** by task type: category-level traversal tasks (T1.3, T2.3) benefit significantly, while leaf-level tasks (T1.4, T1.5) are severely harmed. The mechanism is vocabulary coverage — the 111-node tool graph covers only a fraction of the 1,175-node question space, causing models to anchor on "not found" signals and abandon correct reasoning.

See [docs/BENCHMARK_DESIGN.md](docs/BENCHMARK_DESIGN.md) for the full experimental design.

---

## Quick Start — Running the Benchmark

### 1. Install

```bash
git clone https://github.com/b05611038/flavor_graph_traverser.git
cd flavor_graph_traverser
pip install -r requirements.txt
pip install -e .
```

### 2. Download the benchmark questions

Download `benchmark_questions.json` from the dataset record:

> https://doi.org/10.5281/zenodo.20339333

Place it at `data/questions/benchmark_questions.json`.

### 3. Option A — Cloud LLMs via OpenRouter

Set your API key:

```bash
cp .env.example .env
# Add your key to .env:
# OPENROUTER_API_KEY=sk-or-v1-...
```

Run a quick test (10 questions):

```bash
python scripts/experiment/run_experiment.py \
  --client openrouter \
  --graph data/graphs/coffee_flavor_wheel.json \
  --questions data/questions/benchmark_questions.json \
  --models anthropic/claude-sonnet-4.6 \
  --conditions no_tool tool \
  --max-questions 10 \
  --yes
```

Run the full benchmark (275 questions):

```bash
python scripts/experiment/run_experiment.py \
  --client openrouter \
  --graph data/graphs/coffee_flavor_wheel.json \
  --questions data/questions/benchmark_questions.json \
  --models anthropic/claude-sonnet-4.6 \
  --conditions no_tool tool \
  --yes
```

### 3. Option B — Local LLMs via vLLM

If you have a GPU server running a local model, start a vLLM server first:

```bash
vllm serve <your-model-id> --host 0.0.0.0 --port 8000
```

Then run the benchmark pointing at your server:

```bash
python scripts/experiment/run_experiment.py \
  --client vllm \
  --base-url http://localhost:8000/v1 \
  --graph data/graphs/coffee_flavor_wheel.json \
  --questions data/questions/benchmark_questions.json \
  --models <your-model-id> \
  --conditions no_tool tool \
  --yes
```

The vLLM client uses the OpenAI-compatible `/v1/chat/completions` endpoint and requires no API key. Models must support function calling for the tool condition.

> **Note:** Use `--graph data/graphs/coffee_flavor_wheel.json` (JSON format). The `.pkl` binary format is not included in the repository.

### Useful flags

| Flag | Description |
|---|---|
| `--max-questions N` | Evaluate only the first N questions (quick test) |
| `--sample N` | Sample N questions per task type (representative smoke test across all 9 types) |
| `--no-judge` | Skip LLM-as-judge scoring for F-category questions |
| `--judge-model MODEL_ID` | Override the judge model (default: from `configs/models.yaml`) |
| `--yes` | Skip the confirmation prompt before running |
| `--no-cache` | Disable per-question result caching |

### F-category scoring (open-ended questions)

The 15 F-category questions are scored by an LLM judge (0–5 rubric). By default the judge model is read from `configs/models.yaml`. If you do not have a judge model configured, either:
- Pass `--judge-model anthropic/claude-opus-4.6` (OpenRouter), or
- Pass `--no-judge` to skip F-category scoring entirely (A/E task results are unaffected).

### Results

Results are saved to `results/experiment_YYYYMMDD_HHMMSS/results.json`. The top-level `summary` field contains:
- `macro_score` — equal-weighted mean across 9 task types (primary metric in the paper)
- `by_condition` — scores split by `no_tool` vs `tool`
- `by_task_type` — per-task-type breakdown (A1–A5, E1–E3, F)

---

## Library Quick Start

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

The paper is currently under review and has no DOI or preprint. Citation information will be added here upon publication.

To cite the benchmark dataset:

```bibtex
@dataset{chang2026dataset,
  title   = {FlavorReasonBench-Coffee: Benchmark Dataset},
  author  = {Chang, Yu-Tang and Chen, Shih-Fang},
  year    = {2026},
  doi     = {10.5281/zenodo.20339333},
  url     = {https://doi.org/10.5281/zenodo.20339333}
}
```

---

## Acknowledgments

- Coffee flavor wheel taxonomy: Specialty Coffee Association (SCA)
- Tool-augmented LLM research community
- Hierarchical reasoning benchmark literature
