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

Tool-augmented LLMs achieve near-full-context accuracy with significantly lower token cost, making them practical for deployable sensory recommendation systems.

### Key Comparisons

- **C2 vs C0**: How much do tools help?
- **C1 vs C0**: Does structured reasoning alone help without tools?
- **C3 vs C2**: Does Chain-of-Thought improve tool-augmented reasoning?

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

print(graph.children_of_description('floral'))
# ['rose', 'jasmine', 'lavender', ...]

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

# Get parent (COUNTED — toward 3-call limit)
result = executor.get_parent('rose')
# {'descriptor': 'rose', 'parents': ['floral (middle layer)'], 'error': None}
```

### 3. Run a Benchmark Evaluation

```python
from FlavorGraphTraverser.evaluation import create_client, GraphToolExecutor, QuestionEvaluator

client = create_client("openrouter", "anthropic/claude-sonnet-4.5")
evaluator = QuestionEvaluator(client, executor, "C3")
result = evaluator.evaluate(question)

print(f"Correct: {result.is_correct}, Reasoning calls: {result.metrics.reasoning_calls}")
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
│   ├── client/                 # LLM client abstraction (Ollama, OpenRouter)
│   ├── tools/                  # Graph tool interface (function calling)
│   ├── utils/                  # Answer parser, config loader
│   ├── evaluator.py            # QuestionEvaluator — single-question loop
│   └── batch_runner.py         # BatchRunner — multi-question/model/condition
│
└── generation/                 # Question generation
    ├── question_generator.py   # QuestionGenerator orchestrator
    ├── samplers.py             # Descriptor sampling strategies
    └── validators.py           # Question validation (incl. leakage checks)

configs/                        # YAML configuration files
├── models.yaml                 # 11 models + judge
├── conditions.yaml             # C0–C3 with prompts
├── experiment.yaml             # Experiment configuration
└── README.md                   # Configuration guide

data/                           # Data files (private, excluded from git)
├── graphs/                     # Graph .pkl files
├── filtering/                  # Filtered nodes + exception lists
└── questions/                  # Generated benchmark questions

scripts/                        # Executable scripts
├── generate_all_questions.py   # Generate all question types
├── question_auditor_unified.py # Web-based question auditor
├── manage_queue.py             # Audit queue management
├── backup_manager.py           # Question backup/restore
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
python scripts/generate_all_questions.py

# Generate specific task type(s)
python scripts/generate_all_questions.py E3
python scripts/generate_all_questions.py E2 E3 --count 200
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

### Conditions (C0–C3)

| Condition | Tools | CoT | Max Reasoning Calls | Description |
|-----------|-------|-----|---------------------|-------------|
| **C0** | ✗ | ✗ | — | Zero-shot baseline |
| **C1** | ✗ | ✓ | — | CoT with structural hint |
| **C2** | ✓ | ✗ | 3 | Tools only |
| **C3** | ✓ | ✓ | 3 | CoT + Tools |

### Tool Interface

Three tools exposed to LLMs:

1. **`validate_descriptors`** (FREE, unlimited) — check if descriptors exist in graph
2. **`get_parent`** (COUNTED, max 3 shared) — get parent node(s) of a descriptor
3. **`get_children`** (COUNTED, max 3 shared) — get child node(s) of a descriptor

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
| **F** Open | F Open Reasoning | 15 | In progress |

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
| [docs/BENCHMARK_DESIGN.md](docs/BENCHMARK_DESIGN.md) | Experimental design, conditions, tool interface, metrics |
| [docs/QUESTION_GENERATION.md](docs/QUESTION_GENERATION.md) | Generation pipeline, leakage prevention, validation |
| [docs/AUDITING.md](docs/AUDITING.md) | Audit workflow, queue management, backups |
| [docs/TESTING.md](docs/TESTING.md) | Test suite, fixtures, CI |
| [docs/RESEARCH_POSITION.md](docs/RESEARCH_POSITION.md) | Design philosophy, F-question rationale |
| [configs/README.md](configs/README.md) | YAML configuration reference |

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

## Expected Outputs

1. **Table 1**: Accuracy (%) by Model × Condition (C0–C3)
2. **Table 2**: Per-task breakdown (A1–A5, E1–E3, F)
3. **Figure 1**: Accuracy vs. tool calls — diminishing returns
4. **Figure 2**: Token cost vs. accuracy trade-off
5. **Statistical analysis**: McNemar's test with Bonferroni correction

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
