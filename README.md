# FlavorGraphTraverser

> Benchmarking Tool-Augmented LLM Inference on Coffee Flavor Hierarchy Reasoning

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-47%20passed-success)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Python library for representing and traversing coffee flavor hierarchies as directed acyclic graphs (DAGs). This package enables benchmarking of LLM inference on hierarchical reasoning tasks using the coffee flavor wheel taxonomy.

## 📋 Table of Contents

- [Research Overview](#research-overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Experimental Setup](#experimental-setup)
- [Architecture](#architecture)
- [Testing](#testing)
- [Documentation](#documentation)
- [Citation](#citation)

---

## Research Overview

### Research Question

For domain-specific hierarchical reasoning, how does tool-augmented inference compare to direct prompting?

### Thesis

Tool-augmented LLMs achieve near-full-context accuracy with significantly lower token cost, making them practical for deployable sensory recommendation systems.

### Key Comparisons

- **C2 vs C0**: How much do tools help?
- **C1 vs C0**: Does structural hint alone help without tools?
- **C3 vs C2**: Does Chain-of-Thought improve tool-augmented reasoning?

---

## Quick Start

### 1. Basic Graph Operations

```python
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph

# Load pre-packed graph
data = load_graph_data('data/graphs/coffee_flavor_wheel.pkl')
graph = CoffeeDescriptionGraph(
    data['descriptions'],
    data['connections'],
    root=data['root']
)

# Query graph structure
print(graph.children_of_description('floral'))
# ['rose', 'jasmine', 'lavender', ...]

print(graph.parents_of_description('rose'))
# ['floral (middle layer)']

# Find paths
paths = graph.pathways_between_descriptions('ROOT:SYSTEM', 'rose')
print(paths[0])
```

### 2. Use Graph Tools with LLMs

```python
from FlavorGraphTraverser.evaluation.client import create_client, Message
from FlavorGraphTraverser.evaluation.tools import GraphToolExecutor, get_tool_definitions

# Load graph
data = load_graph_data('data/graphs/coffee_flavor_wheel.pkl')
graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])

# Create tool executor
executor = GraphToolExecutor(graph)

# Validate descriptors (FREE - not counted)
result = executor.validate_descriptors(['rose', 'chocolate', 'unknown'])
print(result)
# {'valid': ['rose', 'chocolate'], 'invalid': ['unknown']}

# Get parent (COUNTED - toward 3-call limit)
result = executor.get_parent('rose')
print(result)
# {'descriptor': 'rose', 'parents': ['floral (middle layer)'], 'error': None}

# Query LLM with tools (Ollama for testing)
client = create_client(
    client_type="ollama",
    model="tinyllama",
    base_url="http://localhost:11434"
)

messages = [Message(role="user", content="What is the parent of 'rose'?")]
response = client.query(messages)
print(response.content)
```

### 3. Run Tests

```bash
# All tests
pytest

# Quick tests (no Ollama required)
./scripts/run_tests.sh quick

# With coverage
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
# Copy environment template
cp .env.example .env

# Edit .env and add your API key
# OPENROUTER_API_KEY=sk-or-v1-...
```

### Dependencies

- `numpy>=1.19.0` - Array operations and matrix representations
- `python-igraph>=0.10.0` - Graph data structure and algorithms
- `requests>=2.25.0` - HTTP client for API calls
- `pyyaml>=5.4.0` - Configuration files

---

## Experimental Setup

### Conditions (C0-C3)

| Condition | Tools | CoT | Max Reasoning Calls | Description |
|-----------|-------|-----|---------------------|-------------|
| **C0** | ✗ | ✗ | - | Zero-shot baseline |
| **C1** | ✗ | ✓ | - | CoT with structural hint |
| **C2** | ✓ | ✗ | 3 | Tools only |
| **C3** | ✓ | ✓ | 3 | CoT + Tools (full) |

### Models (11 Total)

**Closed-Source (4):**
- Claude Sonnet 4.5 (Anthropic)
- GPT-5.2 (OpenAI)
- Gemini 3 Flash (Google)
- Grok 4.1 Fast (xAI)

**Open-Source (7):**
- GPT-OSS 120B, Qwen3-235B-A22B, Kimi K2, Llama 4 Maverick, DeepSeek Chat, Mistral Medium 3, Nemotron Super 49B

**Judge:**
- Claude Opus 4.5 (for F-category questions)

### Tool Interface

Three tools exposed to LLMs:

1. **`validate_descriptors`** (FREE, unlimited)
   - Check if descriptors exist in graph
   - Prevents name mismatch penalties
   - Max 10 descriptors per call

2. **`get_parent`** (COUNTED toward 3-call limit)
   - Get parent node(s) of a descriptor
   - Returns list of parent names

3. **`get_children`** (COUNTED toward 3-call limit)
   - Get child node(s) of a descriptor
   - Returns list of child names

### Evaluation Logic (How We Test LLMs)

#### Turn-Based Interaction Flow

For tool-augmented conditions (C2, C3), each question follows this turn structure:

```
┌─────────────────────────────────────────────┐
│ Turn 1: Initial Query                      │
│ - LLM receives question + tool definitions │
│ - Can call validate_descriptors (FREE)     │
│ - Can call get_parent/get_children (#1)    │
│ - Can answer directly                      │
└─────────────────────────────────────────────┘
         │
         ▼ (if tool called)
┌─────────────────────────────────────────────┐
│ Turn 2: After Tool Result                  │
│ - LLM sees question + tool result history  │
│ - Can call validate_descriptors (FREE)     │
│ - Can call get_parent/get_children (#2)    │
│ - Can answer directly                      │
└─────────────────────────────────────────────┘
         │
         ▼ (if tool called)
┌─────────────────────────────────────────────┐
│ Turn 3: After 2nd Tool Result              │
│ - LLM sees full conversation history       │
│ - Can call validate_descriptors (FREE)     │
│ - Can call get_parent/get_children (#3)    │
│ - Can answer directly                      │
└─────────────────────────────────────────────┘
         │
         ▼ (if tool called or no answer)
┌─────────────────────────────────────────────┐
│ Forced Answer: After 3 Reasoning Calls     │
│ - System: "Provide your final answer now"  │
│ - LLM MUST answer (no more tool calls)     │
└─────────────────────────────────────────────┘
```

**Key Rules:**
- `validate_descriptors`: FREE, unlimited, can be called at start of any turn
- `get_parent` / `get_children`: COUNTED, max 3 total (shared limit)
- Answer can come at any time, or is forced after 3 reasoning calls
- Each turn includes full conversation history

#### Condition-Specific Behavior

**C0 (Zero-shot baseline):**
```python
# Single turn, no tools
system_prompt = "You are an expert in coffee flavor analysis. Answer directly."
messages = [system_prompt, question]
response = llm.query(messages)
answer = parse_answer(response)
```

**C1 (CoT with structural hint):**
```python
# Single turn, no tools, with CoT prompt
system_prompt = """You are an expert in coffee flavor analysis.

Flavor descriptors are organized in a hierarchical graph structure
(e.g., 'strawberry' → 'berry' → 'fruity'). Let's think step-by-step."""

messages = [system_prompt, question]
response = llm.query(messages)
answer = parse_answer(response)
```

**C2 (Tools only):**
```python
# Multi-turn with tools, no CoT hint
system_prompt = "You are an expert with access to a flavor graph database."
messages = [system_prompt, question]
reasoning_calls = 0

while reasoning_calls < 3:
    response = llm.query(messages, tools=tools)

    # Process tool calls
    if response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call.name in ["get_parent", "get_children"]:
                reasoning_calls += 1
            result = executor.execute(tool_call.name, tool_call.args)
            messages.append(tool_result_message(result))

    # Check for answer
    if has_answer(response):
        return parse_answer(response)

# Force answer after 3 calls
messages.append("Provide your final answer now.")
response = llm.query(messages)
answer = parse_answer(response)
```

**C3 (CoT + Tools):**
```python
# Same as C2, but system_prompt includes structural hint (like C1)
system_prompt = """You are an expert with access to a flavor graph database.

Flavor descriptors are organized in a hierarchical graph structure
(e.g., 'strawberry' → 'berry' → 'fruity'). Let's think step-by-step.

Use the tools to query the hierarchy and answer the question."""

# ... rest same as C2
```

#### Answer Extraction

Answers are extracted using regex pattern matching (priority order):

```python
def parse_answer(response_text: str) -> Optional[str]:
    """Extract A/B/C/D answer from LLM response."""
    patterns = [
        r"I select \(([A-D])\)",           # Primary: "I select (B)"
        r"answer is \(([A-D])\)",          # Fallback: "answer is (B)"
        r"\(([A-D])\)",                    # Last standalone (B)
        r"\b([A-D])\b(?!.*\b[A-D]\b)",     # Last standalone letter
    ]

    for pattern in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return None  # Parse error → marked as incorrect
```

#### Metrics Collection

For each question, we record:

```python
{
    "question_id": "A1_001",
    "model": "anthropic/claude-sonnet-4.5",
    "condition": "C2",
    "result": {
        "model_answer": "B",
        "correct_answer": "B",
        "is_correct": true,
        "status": "success"  # or "parse_error", "api_error", "refusal"
    },
    "metrics": {
        "reasoning_calls": 2,
        "validation_calls": 1,
        "total_turns": 3,
        "input_tokens": 850,
        "output_tokens": 120,
        "total_tokens": 970,
        "latency_ms": 2340
    },
    "conversation_history": [...],  # Full trace
    "timestamp": "2026-01-30T14:30:10Z"
}
```

#### Statistical Analysis

Aggregate metrics across all runs:
- **Accuracy by condition** (C0 vs C1 vs C2 vs C3)
- **Accuracy by task type** (A1-A5, E1-E3, F)
- **Accuracy by model** (11 models comparison)
- **Token usage** (cost analysis)
- **Tool usage patterns** (avg reasoning calls, validation calls)
- **McNemar's test** (pairwise condition comparison with Bonferroni correction)

### Question Dataset (~275 questions)

**Category A: Taxonomic Reasoning (180)**
- A1: Root classification (50) ✅ **Audited - 50/50 confirmed**
- A2: Ancestor verification (50)
- A3: Sibling identification (30)
- A4: Path reconstruction (30)
- A5: Lowest common ancestor (20)

**Category E: Similarity Reasoning (80)**
- E1: Similarity ranking (30)
- E2: Pairwise comparison (30)
- E3: Odd one out (20)

**Category F: Open Reasoning (10-15, LLM-judged)**

**A1 Audit Highlights:**
- Multi-label format: 0-N correct answers per question
- Balanced distribution across 9 root categories (5-15 per category)
- Data leakage prevention: Excluded 137 tool graph nodes
- See [docs/A1_QUESTION_AUDIT.md](docs/A1_QUESTION_AUDIT.md) for full audit report

---

## Architecture

```
FlavorGraphTraverser/
├── __init__.py                 # Main package exports
├── graph.py                    # CoffeeDescriptionGraph - DAG representation
├── utils.py                    # Type validation utilities
├── constants.py                # Default connection weights
├── flavor_categories.py        # Reference flavor hierarchy (9 categories)
├── loader.py                   # Graph loading utilities
│
└── evaluation/                 # Benchmarking infrastructure
    ├── client/                 # LLM client abstraction
    │   ├── base.py             # BaseClient abstract class
    │   ├── ollama.py           # OllamaClient (local testing)
    │   ├── openrouter.py       # OpenRouterClient (API)
    │   └── __init__.py         # create_client() factory
    │
    ├── tools/                  # Graph tool interface
    │   ├── definitions.py      # Function calling schemas
    │   ├── executor.py         # GraphToolExecutor
    │   └── __init__.py         # Exports
    │
    ├── judge/                  # (Coming soon) LLM judge for F-category
    └── utils/                  # (Coming soon) Logging, metrics

configs/                        # YAML configuration files
├── models.yaml                 # Model definitions (11 models + judge)
├── conditions.yaml             # C0-C3 definitions with prompts
├── experiment.yaml             # Experiment configuration
└── README.md                   # Configuration guide

data/                           # Data files (private)
├── graphs/                     # Graph .pkl files
├── filtering/                  # Filtered nodes + exception lists
└── questions/                  # Generated questions

scripts/                        # Executable scripts
├── dump_graphs.py              # Extract graphs from database
├── flavor_filter.py            # Hierarchical filtering pipeline
├── review_filtered_nodes.py    # Quality review tool
├── generate_questions.py       # Question generator
└── run_tests.sh                # Test runner

tests/                          # Test suite (47 tests, all passing)
├── client/                     # Client layer tests
├── tools/                      # Tool interface tests
└── integration/                # Integration tests
```

---

## Testing

### Test Suite

Comprehensive test coverage with 47 tests across 3 categories:

```bash
# Run all tests (47 tests)
pytest

# Run specific test categories
./scripts/run_tests.sh unit          # Unit tests only
./scripts/run_tests.sh integration   # Integration tests
./scripts/run_tests.sh quick         # Tests without Ollama

# Generate coverage report
./scripts/run_tests.sh coverage
```

### Test Categories

**Unit Tests (39 tests)**
- `tests/client/test_base.py` - Abstract client interface (9 tests)
- `tests/client/test_ollama.py` - Ollama client (7 tests)
- `tests/tools/test_definitions.py` - Tool schemas (7 tests)
- `tests/tools/test_executor.py` - Tool executor (16 tests)

**Integration Tests (8 tests)**
- `tests/integration/test_client_tools_integration.py` - Full workflow tests

### Continuous Testing

```bash
# Install pytest-watch for auto-running tests
pip install pytest-watch

# Watch mode
./scripts/run_tests.sh watch
```

---

## Documentation

### Core Documentation

- **[Implementation Guide](docs/FlavorGraphTraverser_Implementation_Guide.md)** - Complete design specification
- **[Configuration Guide](configs/README.md)** - YAML config reference
- **[Filtering Workflow](docs/FILTERING_WORKFLOW.md)** - Node filtering and quality control
- **[CONFIG Reference](docs/CONFIG.md)** - Filtering parameters
- **[QUESTIONS](docs/QUESTIONS.md)** - Question templates

### Module Documentation

- **[Evaluation Module README](FlavorGraphTraverser/evaluation/README.md)** - Evaluation framework details

### Quick Links

- **Question Templates**: [docs/QUESTIONS.md](docs/QUESTIONS.md)
- **Methodology**: [docs/CLAUDE.md](docs/CLAUDE.md)
- **Examples**: [examples/](examples/)

---

## Core API: CoffeeDescriptionGraph

Main class for DAG representation of flavor relationships.

### Key Methods

**Graph Queries:**
```python
graph.children_of_description(desc)     # Get direct descendants
graph.parents_of_description(desc)      # Get direct ancestors
graph.get_connection(desc1, desc2)      # Get connection type
```

**Path Finding:**
```python
graph.pathways_between_descriptions(from, to, k=1)  # K shortest paths
graph.distance_between_descriptions(from, to)       # Shortest distance
```

**Graph Analysis:**
```python
graph.valid_construction()              # Verify DAG property
graph.subgraph_induced_from_description(desc)  # Extract subgraph
graph.adjacency_matrix()                # Get matrix representation
```

**Visualization:**
```python
graph.plot(filename)                    # Save graph visualization
```

See [examples/example_load_graph.py](examples/example_load_graph.py) for complete usage examples.

---

## Expected Outputs

1. **Table 1: Main Results** - Accuracy (%) by Model × Condition (C0-C3)
2. **Table 2: Per-Task Breakdown** - Accuracy across task types (A1-A5, E1-E3, F)
3. **Figure 1: Accuracy vs Tool Calls** - Diminishing returns (C0 → C2 → C3)
4. **Figure 2: Token Cost vs Accuracy** - Trade-off scatter plot
5. **Statistical Analysis** - McNemar's test with Bonferroni correction

---

## Success Criteria

1. ✅ Tool-augmented (C2/C3) achieves ≥90% of direct prompting baseline
2. ✅ Clear accuracy/cost trade-off curve established
3. ✅ Results statistically significant (p < 0.05)
4. ✅ Actionable deployment recommendation

---

## Budget Estimate

```
Total runs: 275 questions × 4 conditions × 11 models = 12,100 runs
Est. tokens/run: ~800 average
Total tokens: ~9.7M

Cost breakdown:
- Closed-source: ~$15-25
- Open-source: ~$9-19
- Judge (F-category): ~$5-8

Total: ~$35-55
```

---

## Project Status

### ✅ Implemented (Ready for Use)

- **Core graph library** - CoffeeDescriptionGraph with full API
- **Filtering pipeline** - Hierarchical filtering with exception lists (892/1,175 nodes)
- **Question generation** - 255/275 questions generated (A1-A5, E1-E3, F)
- **LLM client abstraction** - Switch between Ollama (local) and OpenRouter (API)
- **Graph tool interface** - validate_descriptors, get_parent, get_children
- **Configuration system** - YAML configs for models, conditions, experiments
- **Test suite** - 47 tests passing (unit + integration)
- **Documentation** - Comprehensive guides and examples

### ⏳ In Progress (Next Phase)

- **Evaluator/Runner** - Turn-based evaluation loop (NOT IMPLEMENTED)
  - Condition handlers (C0-C3 logic)
  - Turn structure manager
  - Answer parser
  - Result caching
- **Metrics collection** - Token usage, accuracy tracking
- **Logging system** - CLI display + file output
- **LLM judge** - For F-category questions
- **Statistical analysis** - McNemar's test, result tables

### ⚠️ Can We Run Experiments Now?

**NO** - The evaluator layer is not implemented.

**What we have:**
- ✅ Can create clients and tools
- ✅ Can call LLMs manually
- ✅ Can execute individual tool calls

**What we're missing:**
- ❌ Turn-based evaluation loop
- ❌ Condition-specific prompting logic
- ❌ Automatic answer extraction
- ❌ Metrics aggregation
- ❌ Batch processing across questions

**See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for detailed gap analysis.**

**Estimated time to completion:** 1-2 days for basic evaluator, 3-5 days for full system

---

## Contributing

This is a research project. For questions or suggestions, please open an issue.

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

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

Part of the IR-BERT Coffee Chat System project. Built with Claude Sonnet 4.5.

**Related Work:**
- Coffee flavor wheel taxonomy (Specialty Coffee Association)
- Tool-augmented LLM research
- Hierarchical reasoning benchmarks
