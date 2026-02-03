# Evaluation Module

Infrastructure for benchmarking tool-augmented LLM inference on coffee flavor hierarchy reasoning.

## Overview

This module provides:
- **Abstract LLM client layer** - Switch between Ollama (local) and OpenRouter (API)
- **Graph tool interface** - Expose CoffeeDescriptionGraph as LLM tools
- **Evaluation framework** - Run experiments across models and conditions (coming soon)
- **Metrics and logging** - Track accuracy, token usage, and tool calls (coming soon)

## Quick Start

### 1. Test Graph Tools

```python
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.evaluation.tools import GraphToolExecutor, get_tool_definitions

# Load graph
data = load_graph_data('data/graphs/coffee_flavor_wheel.pkl')
graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])

# Create executor
executor = GraphToolExecutor(graph)

# Validate descriptors
result = executor.validate_descriptors(['rose', 'chocolate', 'unknown'])
print(result)
# {'valid': ['rose', 'chocolate'], 'invalid': ['unknown']}

# Get parent
result = executor.get_parent('rose')
print(result)
# {'descriptor': 'rose', 'parents': ['floral'], 'error': None}

# Get children
result = executor.get_children('floral')
print(result)
# {'descriptor': 'floral', 'children': ['rose', 'jasmine', ...], 'error': None}
```

### 2. Test LLM Client (Ollama)

```python
from FlavorGraphTraverser.evaluation.client import create_client, Message

# Create Ollama client
client = create_client(
    client_type="ollama",
    model="tinyllama",
    base_url="http://localhost:11434"
)

# Check availability
print(f"Available: {client.is_available()}")
print(f"Models: {client.list_models()}")

# Query
messages = [Message(role="user", content="What is 2+2?")]
response = client.query(messages)
print(response.content)
print(f"Tokens: {response.usage}")
```

### 3. Test with Function Calling

```python
from FlavorGraphTraverser.evaluation.client import create_client, Message
from FlavorGraphTraverser.evaluation.tools import get_tool_definitions

# Create client
client = create_client(client_type="ollama", model="tinyllama")

# Get tool definitions
tools = get_tool_definitions()

# Query with tools (if model supports function calling)
messages = [
    Message(role="user", content="Check if 'rose' and 'chocolate' are valid descriptors.")
]

response = client.query(messages, tools=tools)
print(response.tool_calls)  # Model may call validate_descriptors
```

### 4. Run Tests

```bash
# From project root
python examples/test_client_and_tools.py
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
│   ├── executor.py       # GraphToolExecutor (wraps CoffeeDescriptionGraph)
│   └── __init__.py       # Exports
│
├── judge/                # (Coming soon) LLM judge for F-category
├── utils/                # (Coming soon) Logging, file I/O
└── README.md             # This file
```

## Configuration

See `configs/` directory for YAML configuration files:
- `models.yaml` - Model definitions (11 models + judge)
- `conditions.yaml` - Experimental conditions (C0-C3)
- `experiment.yaml` - Main experiment config

## Environment Variables

```bash
# Required for OpenRouter
export OPENROUTER_API_KEY="sk-or-v1-..."

# Optional overrides
export OLLAMA_HOST="http://localhost:11434"
```

See `.env.example` for complete list.

## Client Types

### Ollama (Local Testing)

- **Host**: http://localhost:11434
- **Model**: TinyLlama (currently running)
- **Cost**: Free
- **Use case**: Debug and test code without API costs

```python
client = create_client(
    client_type="ollama",
    model="tinyllama",
    base_url="http://localhost:11434"
)
```

### OpenRouter (Production)

- **Providers**: OpenAI, Anthropic, Google, xAI, Meta, etc.
- **Models**: 11 models configured (4 closed-source, 7 open-source)
- **Cost**: Pay-per-use (see `configs/models.yaml` for pricing)
- **Use case**: Full benchmark experiments

```python
client = create_client(
    client_type="openrouter",
    model="anthropic/claude-sonnet-4.5",
    api_key=os.getenv("OPENROUTER_API_KEY")
)
```

## Graph Tools

Three tools are exposed to LLMs:

### 1. `validate_descriptors` (FREE)

Check if descriptors exist in the graph.

- **Cost**: Free, unlimited calls
- **Purpose**: Prevent name mismatch penalties
- **Batch size**: Max 10 descriptors per call

```python
result = executor.validate_descriptors(['rose', 'chocolate', 'unknown'])
# {'valid': ['rose', 'chocolate'], 'invalid': ['unknown']}
```

### 2. `get_parent` (COUNTED)

Get parent node(s) of a descriptor.

- **Cost**: Counted toward 3-call reasoning limit
- **Returns**: List of parent names

```python
result = executor.get_parent('rose')
# {'descriptor': 'rose', 'parents': ['floral'], 'error': None}
```

### 3. `get_children` (COUNTED)

Get child node(s) of a descriptor.

- **Cost**: Counted toward 3-call reasoning limit
- **Returns**: List of child names

```python
result = executor.get_children('floral')
# {'descriptor': 'floral', 'children': ['rose', 'jasmine', ...], 'error': None}
```

## Error Handling

Tools return error information when descriptors don't exist:

```python
result = executor.get_parent('invalid_node')
# {
#   'descriptor': 'invalid_node',
#   'parents': None,
#   'error': "Descriptor 'invalid_node' not found in graph. Use validate_descriptors first."
# }
```

## Next Steps

- [ ] Implement evaluator with turn structure
- [ ] Implement answer parser
- [ ] Implement LLM judge for F-category questions
- [ ] Implement main runner script
- [ ] Add logging and metrics collection

## See Also

- `docs/FlavorGraphTraverser_Implementation_Guide.md` - Complete design specification
- `configs/README.md` - Configuration guide
- `examples/test_client_and_tools.py` - Integration test examples
