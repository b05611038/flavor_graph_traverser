# Evaluation Module

Infrastructure for benchmarking tool-augmented LLM inference on coffee flavor hierarchy reasoning.

## Overview

This module provides:
- **Abstract LLM client layer** — Switch between Ollama (local) and OpenRouter (API)
- **Graph tool interface** — Expose CoffeeDescriptionGraph as LLM tools
- **Evaluation framework** — Turn-based evaluation loop across C0–C3 conditions
- **Batch runner** — Run experiments across multiple questions, models, and conditions with caching
- **Answer parser** — Priority-based extraction from LLM responses
- **Metrics collection** — Accuracy, token usage, latency, tool call tracking

## Quick Start

### Test Graph Tools

```python
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.evaluation.tools import GraphToolExecutor, get_tool_definitions

data = load_graph_data('data/graphs/coffee_flavor_wheel.pkl')
graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])
executor = GraphToolExecutor(graph)

executor.validate_descriptors(['rose', 'chocolate', 'unknown'])
# {'valid': ['rose', 'chocolate'], 'invalid': ['unknown']}

executor.get_parent('rose')
# {'descriptor': 'rose', 'parents': ['floral'], 'error': None}
```

### Run a Single Evaluation

```python
from FlavorGraphTraverser.evaluation import create_client, GraphToolExecutor, QuestionEvaluator

client = create_client("openrouter", "anthropic/claude-sonnet-4.5")
evaluator = QuestionEvaluator(client, executor, "C3")
result = evaluator.evaluate(question)

print(result.is_correct, result.metrics.reasoning_calls, result.metrics.total_tokens)
```

### Run Batch Evaluation

```python
from FlavorGraphTraverser.evaluation import BatchRunner

runner = BatchRunner(
    questions_file="data/questions/all_questions_system.json",
    graph_file="data/graphs/coffee_flavor_wheel.pkl",
    output_dir="results/benchmark"
)
results = runner.run(
    models=["anthropic/claude-sonnet-4.5"],
    conditions=["C0", "C2", "C3"],
    client_type="openrouter"
)
```

## Module Structure

```
FlavorGraphTraverser/evaluation/
├── client/
│   ├── base.py           # BaseClient abstract class
│   ├── ollama.py         # OllamaClient (local testing)
│   ├── openrouter.py     # OpenRouterClient (API)
│   └── __init__.py       # create_client() factory
│
├── tools/
│   ├── definitions.py    # Tool schemas for function calling
│   ├── executor.py       # GraphToolExecutor
│   └── __init__.py
│
├── utils/
│   ├── answer_parser.py  # Priority-based answer extraction
│   ├── config_loader.py  # YAML condition loader
│   └── __init__.py
│
├── evaluator.py          # QuestionEvaluator (single-question evaluation)
└── batch_runner.py       # BatchRunner (multi-question/model/condition)
```

## Configuration

See `configs/` for YAML configuration:
- `models.yaml` — Model definitions (11 models + judge)
- `conditions.yaml` — C0–C3 definitions with prompts
- `experiment.yaml` — Experiment configuration

## Environment Variables

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export OLLAMA_HOST="http://localhost:11434"  # optional override
```

## See Also

- `docs/BENCHMARK_DESIGN.md` — Full benchmark design and turn structure
- `configs/README.md` — Configuration guide
