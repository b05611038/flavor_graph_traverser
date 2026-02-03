# Configuration Guide

This directory contains YAML configuration files for the FlavorGraphTraverser evaluation framework.

## Files

- **`models.yaml`**: Model definitions (closed-source, open-source, local, judge)
- **`conditions.yaml`**: Experimental conditions (C0-C3) with prompts
- **`experiment.yaml`**: Main experiment configuration

## Quick Start

### 1. Set Environment Variables

```bash
# For OpenRouter API (required for full benchmark)
export OPENROUTER_API_KEY="your_api_key_here"

# Optional: Custom paths
export FLAVOR_GRAPH_DATA="path/to/data"
```

**IMPORTANT**: Never commit API keys to version control. Always use environment variables.

### 2. Choose Run Configuration

Edit `experiment.yaml` and set the appropriate run:

```yaml
runs:
  debug:
    enabled: true   # ← Set to true for local testing
  pilot:
    enabled: false  # ← Set to true for small OpenRouter test
  full:
    enabled: false  # ← Set to true for full benchmark
```

### 3. Select Client

In `experiment.yaml`, choose the client type:

```yaml
client:
  type: "ollama"      # For local testing with TinyLlama
  # type: "openrouter" # For real benchmark with API models
```

---

## Configuration Reference

### models.yaml

Defines all models to test.

#### Structure

```yaml
closed_source:
  - id: anthropic/claude-sonnet-4.5  # OpenRouter model ID
    name: Claude Sonnet 4.5          # Display name
    provider: Anthropic              # Provider name
    pricing:
      input: 3.0                     # $ per 1M input tokens
      output: 15.0                   # $ per 1M output tokens
    enabled: true                    # Include in benchmark?

open_source:
  - id: meta-llama/llama-4-maverick
    name: Llama 4 Maverick
    provider: Meta
    notes: Uses pythonic parser      # Optional notes
    enabled: true

local:
  - id: tinyllama                    # Model name for Ollama
    name: TinyLlama
    provider: Ollama
    host: http://localhost:11434
    enabled: true
    notes: For debugging only

judge:
  id: anthropic/claude-opus-4.5      # Model for F-category judging
  name: Claude Opus 4.5
  provider: Anthropic
```

#### Enabling/Disabling Models

Set `enabled: false` to skip a model without deleting its configuration:

```yaml
  - id: xai/grok-4-1-fast
    enabled: false  # Will be skipped in all runs
```

---

### conditions.yaml

Defines the 4 experimental conditions.

#### Structure

```yaml
conditions:
  C0:
    name: "Zero-shot Baseline"
    description: "Direct prompting without tools or CoT"
    tools_enabled: false
    cot_enabled: false
    max_reasoning_calls: 0
    system_prompt: |
      Your system prompt here...

common:
  temperature: 0              # For determinism
  max_output_tokens: 1024
  timeout_seconds: 60
  answer_format: |
    Answer format instructions...
```

#### Condition Definitions

| Condition | Tools | CoT | Max Calls | Purpose |
|-----------|-------|-----|-----------|---------|
| **C0** | ✗ | ✗ | 0 | Zero-shot baseline |
| **C1** | ✗ | ✓ | 0 | CoT with structural hint |
| **C2** | ✓ | ✗ | 3 | Tools only |
| **C3** | ✓ | ✓ | 3 | Full tool-augmented + CoT |

#### Customizing Prompts

Edit the `system_prompt` field for each condition:

```yaml
  C3:
    system_prompt: |
      You are an expert in coffee flavor analysis...

      [Your custom instructions here]
```

**Note**: Keep the answer format instruction consistent across conditions.

---

### experiment.yaml

Main configuration for running experiments.

#### Key Sections

##### 1. Experiment Metadata

```yaml
experiment:
  name: "flavor_hierarchy_reasoning"
  version: "1.0"
  random_seed: 42  # For reproducibility
```

##### 2. Data Paths

```yaml
data:
  graph_file: "data/graphs/coffee_flavor_wheel.pkl"
  questions_file: "data/questions/questions_complete.json"
```

**Relative to project root**. Adjust if you move data files.

##### 3. Client Configuration

```yaml
client:
  type: "ollama"  # or "openrouter"

  openrouter:
    api_key_env: "OPENROUTER_API_KEY"  # Env var name
    base_url: "https://openrouter.ai/api/v1"
    site_url: "https://github.com/b05611038/flavor_graph_traverser"
    app_name: "FlavorGraphTraverser"

  ollama:
    base_url: "http://localhost:11434"
    default_model: "tinyllama"
```

**Client Types:**
- `ollama`: Local testing with TinyLlama (localhost:11434)
- `openrouter`: API access to all models in `models.yaml`

##### 4. Run Configurations

Define multiple run profiles:

```yaml
runs:
  debug:
    enabled: true
    description: "Quick test with local ollama"
    client_type: "ollama"
    models: ["tinyllama"]
    conditions: ["C0", "C2"]
    max_questions: 5
    question_types: ["A1"]

  pilot:
    enabled: false
    client_type: "openrouter"
    models:
      - "openai/gpt-3.5-turbo"
      - "anthropic/claude-haiku"
    conditions: ["C0", "C2", "C3"]
    max_questions: 10
    question_types: ["A1", "A2", "E1"]

  full:
    enabled: false
    client_type: "openrouter"
    models: "all"  # All enabled models from models.yaml
    conditions: ["C0", "C1", "C2", "C3"]
    max_questions: null  # All questions
    question_types: null  # All types
```

**Run Selection**: Only one run should have `enabled: true` at a time.

**Model Selection**:
- List specific models: `["model1", "model2"]`
- Use all: `"all"`

**Question Filtering**:
- `max_questions: 5` - Limit to first 5 questions
- `max_questions: null` - Use all questions
- `question_types: ["A1", "E1"]` - Only these types
- `question_types: null` - All types

##### 5. Error Handling

```yaml
error_handling:
  max_retries: 3
  retry_backoff: [2, 4, 8]  # Exponential: 2s, 4s, 8s
  timeout_per_call: 60      # seconds
```

##### 6. Caching

```yaml
cache:
  enabled: true
  directory: "results/cache"
  invalidate_on_version_change: true
```

Caches completed question results. Re-run will skip cached questions.

##### 7. Logging

```yaml
logging:
  level: "INFO"  # DEBUG | INFO | WARNING | ERROR
  directory: "logs"
  console_output: true
  save_turn_logs: true
  format: "%(asctime)s [%(levelname)s] %(message)s"
```

##### 8. Output

```yaml
output:
  results_directory: "results"
  save_summary_csv: true
  save_error_report: true
  save_turn_logs: true
```

---

## Environment Variables

### Required for OpenRouter

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Get your key from: https://openrouter.ai/keys

### Optional Overrides

```bash
# Override data paths
export FLAVOR_GRAPH_FILE="/custom/path/graph.pkl"
export FLAVOR_QUESTIONS_FILE="/custom/path/questions.json"

# Override ollama host
export OLLAMA_HOST="http://localhost:11434"

# Override output directory
export RESULTS_DIR="/custom/results"
```

---

## Usage Examples

### Example 1: Debug with Local Ollama

**Goal**: Test implementation with 5 questions on local TinyLlama.

**Config** (`experiment.yaml`):
```yaml
client:
  type: "ollama"

runs:
  debug:
    enabled: true
    client_type: "ollama"
    models: ["tinyllama"]
    conditions: ["C0", "C2"]
    max_questions: 5
```

**Run**:
```bash
python scripts/run_benchmark.py --run debug
```

### Example 2: Pilot Test with 2 Models

**Goal**: Test with OpenRouter API on 10 questions.

**Config**:
```yaml
client:
  type: "openrouter"

runs:
  pilot:
    enabled: true
    models:
      - "openai/gpt-3.5-turbo"
      - "anthropic/claude-haiku"
    conditions: ["C0", "C2", "C3"]
    max_questions: 10
```

**Environment**:
```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

**Run**:
```bash
python scripts/run_benchmark.py --run pilot
```

**Expected cost**: ~$0.10-0.20

### Example 3: Full Benchmark

**Goal**: Run complete experiment with all models and conditions.

**Config**:
```yaml
client:
  type: "openrouter"

runs:
  full:
    enabled: true
    models: "all"
    conditions: ["C0", "C1", "C2", "C3"]
    max_questions: null
```

**Run**:
```bash
python scripts/run_benchmark.py --run full
```

**Expected cost**: ~$35-55 (see Implementation Guide)

---

## Configuration Best Practices

### 1. Version Control

- ✅ **Commit**: Config templates with placeholders
- ❌ **Never commit**: API keys or secrets
- ✅ **Use**: `.env` files (gitignored) for local development

### 2. Testing Workflow

1. Start with `debug` run (ollama, 5 questions)
2. Move to `pilot` run (cheap models, 10 questions)
3. Check results and costs
4. Run `full` benchmark

### 3. Model Selection Strategy

**For cost-effective testing:**
```yaml
models:
  - "openai/gpt-3.5-turbo"      # Cheap, baseline
  - "anthropic/claude-haiku"     # Cheap, Anthropic
  - "google/gemini-3-flash-preview"  # Cheap, Google
```

**For high-quality results:**
```yaml
models:
  - "anthropic/claude-sonnet-4.5"
  - "openai/gpt-5.2"
```

### 4. Caching Strategy

- Keep `cache.enabled: true` during development
- Invalidate cache when changing:
  - Prompts in `conditions.yaml`
  - Tool definitions
  - Question format

---

## Troubleshooting

### API Key Not Found

**Error**: `OpenRouter API key not found in environment`

**Fix**:
```bash
export OPENROUTER_API_KEY="your_key"
# Or add to ~/.bashrc or ~/.zshrc
```

### Ollama Connection Failed

**Error**: `Failed to connect to ollama at localhost:11434`

**Fix**:
1. Check ollama is running: `curl http://localhost:11434`
2. Verify model is available: `ollama list`
3. Check network/firewall settings

### Model Not Found

**Error**: `Model 'xyz' not found in models.yaml`

**Fix**:
1. Add model to `models.yaml`
2. Set `enabled: true`
3. Verify OpenRouter model ID is correct

### Question File Not Found

**Error**: `Questions file not found: data/questions/questions_complete.json`

**Fix**:
1. Generate questions: `python scripts/generate_questions.py`
2. Or update path in `experiment.yaml`

---

## See Also

- `docs/FlavorGraphTraverser_Implementation_Guide.md` - Complete design specification
- `docs/FILTERING_WORKFLOW.md` - Question generation workflow
- `FlavorGraphTraverser/evaluation/README.md` - Evaluation module documentation
