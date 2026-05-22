# Evaluation Module

Infrastructure for benchmarking tool-augmented LLM inference on coffee flavor hierarchy reasoning.

## Overview

This module provides:
- **Abstract LLM client layer** — OpenRouter for production runs; Ollama and vLLM for local testing/validation
- **Graph tool interface** — Expose CoffeeDescriptionGraph as LLM tools with budget control
- **Evaluation framework** — Turn-based evaluation loop across no_tool/tool conditions with forced-answer fallback
- **Batch runner** — Run experiments across multiple questions, models, and conditions with caching and incremental saves
- **Answer parser** — Three-layer extraction pipeline (canonical patterns → model-specific normalization → constrained fallback)
- **Scoring** — Continuous 0–1 scores: binary for single-choice, F1 for multi-select, judge_score/5 for F-category
- **LLM-as-a-judge** — F-category open-ended response evaluation with rubric-based 0–5 scoring
- **Metrics collection** — Accuracy, scores, token usage, latency, tool call tracking (nav/val/turns)

## Quick Start

### Test Graph Tools

```python
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.evaluation.tools import GraphToolExecutor, get_tool_definitions

data = load_graph_data('data/graphs/coffee_flavor_wheel.json')
graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])
executor = GraphToolExecutor(graph)

executor.validate_descriptors(['rose', 'chocolate', 'unknown'])
# {'valid': ['rose', 'chocolate'], 'invalid': ['unknown']}

executor.get_parent('blueberry')
# {'descriptor': 'blueberry', 'parents': ['berry'], 'error': None}
```

### Run a Single Evaluation

```python
from FlavorGraphTraverser.evaluation import create_client, GraphToolExecutor, QuestionEvaluator

client = create_client("openrouter", "anthropic/claude-sonnet-4.6")
evaluator = QuestionEvaluator(client, executor, "tool")
result = evaluator.evaluate(question)

print(result.score, result.is_correct, result.metrics.reasoning_calls)
```

### Run Batch Evaluation

```bash
# Production run via OpenRouter
python scripts/experiment/run_experiment.py \
  --client openrouter \
  --models anthropic/claude-sonnet-4.6 \
  --conditions no_tool tool

# Local smoke test via vLLM (for validation before production runs)
python scripts/experiment/run_experiment.py \
  --client vllm --base-url http://localhost:8000/v1 \
  --models openai/gpt-oss-20b \
  --conditions no_tool tool \
  --sample 1 --judge-model openai/gpt-oss-20b --yes
```

### View Results

```bash
python scripts/audit/question_auditor_unified.py \
  data/questions/all_questions_system.json \
  --results results/merge_all/results.json
# Open http://localhost:5000/results
```

## Module Structure

```
FlavorGraphTraverser/evaluation/
├── client/
│   ├── base.py           # BaseClient abstract class, Message dataclass
│   ├── ollama.py         # OllamaClient (local testing)
│   ├── openrouter.py     # OpenRouterClient (API)
│   ├── vllm.py           # VLLMClient (local testing only, OpenAI-compatible)
│   └── __init__.py       # create_client() factory
│
├── tools/
│   ├── definitions.py    # Tool schemas with budget/limit descriptions
│   ├── executor.py       # GraphToolExecutor
│   └── __init__.py
│
├── utils/
│   ├── answer_parser.py  # Answer extraction + compute_question_score()
│   ├── config_loader.py  # YAML condition loader
│   ├── icl_tools.py      # ICL text-based tool simulation (loads prompts/icl_tools.txt)
│   ├── response_normalizer.py  # Thinking tag removal
│   └── __init__.py
│
├── judge/
│   ├── judge.py          # LLMJudge (loads prompts/judge_system.txt, judge_closing.txt)
│   └── __init__.py
│
├── evaluator.py          # QuestionEvaluator (loads prompts/answer_format_*.txt, forced_answer*.txt, tool_budget.txt)
└── batch_runner.py       # BatchRunner with macro/micro scoring and incremental saves
```

## Prompt Management

All prompt templates are in `prompts/*.txt`. The evaluator, judge, and ICL tools load them via:

```python
from prompts import load_prompt

prompt = load_prompt("tool_budget", max_calls=5)
```

To modify any prompt, edit the `.txt` file — no Python changes needed.

## Configuration

See `configs/` for YAML configuration:
- `models.yaml` — Model definitions (11 models + judge)
- `conditions.yaml` — no_tool/tool condition definitions with neutral system prompts
- `experiment.yaml` — Experiment configuration

## Environment Variables

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export OLLAMA_HOST="http://localhost:11434"  # optional override
```

## See Also

- `docs/BENCHMARK_DESIGN.md` — Full benchmark design, scoring, and turn structure
- `docs/AUDITING.md` — Audit workflow and results viewer
- `configs/README.md` — Configuration guide
- `prompts/` — All prompt templates
