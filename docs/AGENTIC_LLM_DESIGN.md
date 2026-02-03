# Agentic LLM Implementation Design Discussion

## Project Context

Building an evaluation framework to benchmark tool-augmented LLM inference on coffee flavor hierarchy reasoning. Need to support multiple LLMs via OpenRouter and implement different experimental conditions (C0-C5).

---

## 1. Experimental Conditions Definition

**Current status**: `docs/CLAUDE.md` mentions C0-C5 but lacks specific definitions.

**Need to decide:**

### C0: Baseline Direct Prompting
- **Option A**: Zero-shot (no examples, no context)
- **Option B**: Zero-shot + task instruction
- **Question**: What level of instruction is allowed?

### C1: ?
- **Option A**: Few-shot examples (3-5 examples)?
- **Option B**: Basic chain-of-thought prompting?
- **Question**: What differentiates C0 from C1?

### C2: ?
- **Option A**: Enhanced prompting (CoT + examples)?
- **Option B**: Multi-step reasoning without tools?
- **Question**: What's the progression from C1 to C2?

### C3: Tool-Augmented (Limited)
- LLM can query `coffee_flavor_wheel` graph via tools
- **Question**: What's the limit?
  - Max N tool calls (e.g., 3, 5, 10)?
  - Time limit?
  - Token budget?

### C4: Tool-Augmented (Unlimited)
- LLM can query `coffee_flavor_wheel` freely
- **Question**: Any practical limits?
  - Max iterations to prevent infinite loops?
  - Timeout?

### C5: Full-Context Baseline
- Entire SYSTEM graph provided in context
- **Question**: How to format the graph?
  - JSON dump?
  - Structured text (adjacency list)?
  - Natural language description?

**Action items:**
- [ ] Define each condition precisely
- [ ] Specify prompts for C0-C2
- [ ] Define tool call limits for C3-C4
- [ ] Design context format for C5

---

## 2. Tool Interface Design

The LLM needs to query `coffee_flavor_wheel` graph (111 nodes, 110 connections).

### Option A: Function Calling (Native)

**Pros:**
- Clean, structured
- Native support from many LLMs
- Easy to parse and log

**Cons:**
- Requires function calling support
- Not all models support it well

**Example:**
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_children",
        "description": "Get all child nodes of a given flavor node",
        "parameters": {
          "type": "object",
          "properties": {
            "node": {
              "type": "string",
              "description": "The flavor node name"
            }
          },
          "required": ["node"]
        }
      }
    },
    {
      "name": "get_parent",
      "description": "Get the parent node of a given flavor node",
      ...
    },
    {
      "name": "find_path",
      "description": "Find path between two flavor nodes",
      ...
    }
  ]
}
```

### Option B: ReAct-style (Text-based)

**Pros:**
- Works with any LLM
- No function calling required
- Interpretable reasoning trace

**Cons:**
- Requires parsing text output
- More prone to format errors
- Need careful prompt engineering

**Example:**
```
Available Actions:
- get_children(node) - Get all child nodes
- get_parent(node) - Get parent node
- find_path(node1, node2) - Find path between nodes

Format:
Thought: [your reasoning]
Action: [action_name(arguments)]
```

**Output:**
```
Thought: I need to find the parent of "rose"
Action: get_parent("rose")
```

### Option C: Hybrid

- Prefer function calling if available
- Fall back to ReAct for models without support

**Questions:**
- Which approach to use?
- What tools to expose? (children, parent, path, distance, siblings, LCA, ...?)
- Should we expose all FlavorGraphTraverser API methods?

**Action items:**
- [ ] Choose tool interface approach
- [ ] List all available tool functions
- [ ] Design tool function signatures
- [ ] Write tool descriptions for LLM

---

## 3. Architecture Proposal

```
┌─────────────────────────────────────────────────┐
│          Evaluation Framework                   │
│  - Load questions from data/questions/          │
│  - Run experiments across conditions (C0-C5)    │
│  - Run experiments across models                │
│  - Collect metrics (accuracy, token cost)       │
│  - Export results for analysis                  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│          LLM Abstract Layer                     │
│  - BaseClient (abstract interface)              │
│  - OpenRouterClient (implementation)            │
│  - Unified interface: query(prompt, tools)      │
│  - Token tracking, error handling               │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│        Agent/Condition Handler                  │
│  - BaseAgent (abstract)                         │
│  - DirectAgent (C0-C2): no tools                │
│  - ToolAgent (C3-C4): with tool access          │
│  - FullContextAgent (C5): graph in context      │
│  - Each handles prompt construction + execution │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│          Tool Interface                         │
│  - GraphTools: wrapper around CoffeeDescriptionGraph │
│  - Exposes: get_children(), get_parent(), etc.  │
│  - Loads coffee_flavor_wheel.pkl                │
│  - Returns structured results                   │
└─────────────────────────────────────────────────┘
```

### Proposed Code Structure

```
FlavorGraphTraverser/
├── agents/
│   ├── __init__.py
│   ├── base.py              # BaseAgent abstract class
│   ├── direct_agent.py      # C0-C2: Direct prompting handlers
│   ├── tool_agent.py        # C3-C4: Tool-augmented agents
│   └── full_context_agent.py # C5: Full-context handler
│
├── llm/
│   ├── __init__.py
│   ├── base_client.py       # Abstract LLM client interface
│   ├── openrouter_client.py # OpenRouter implementation
│   └── mock_client.py       # Mock client for testing
│
├── tools/
│   ├── __init__.py
│   └── graph_tools.py       # coffee_flavor_wheel tool wrapper
│
├── evaluation/
│   ├── __init__.py
│   ├── evaluator.py         # Main evaluation orchestrator
│   ├── metrics.py           # Accuracy, cost calculation
│   ├── judge.py             # LLM judge for F-type questions
│   └── results.py           # Result export and formatting
│
└── prompts/
    ├── __init__.py
    ├── system_prompts.py    # System prompts for different conditions
    └── templates.py         # Question formatting templates
```

**Questions:**
- Does this structure make sense?
- Any missing components?
- Should prompts be in code or config files?

**Action items:**
- [ ] Finalize folder structure
- [ ] Define interfaces for each component
- [ ] Decide on configuration approach (code vs files)

---

## 4. OpenRouter Integration

### API Basics

**OpenRouter features:**
- OpenAI-compatible API
- Access to multiple model providers
- Built-in cost tracking
- Rate limiting and fallback

**Authentication:**
```python
headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "HTTP-Referer": "https://github.com/b05611038/flavor_graph_traverser",
}
```

### Models to Test

**Recommended models:**
- `openai/gpt-4-turbo-preview` (strong reasoning)
- `openai/gpt-3.5-turbo` (baseline)
- `anthropic/claude-opus` (strong reasoning)
- `anthropic/claude-sonnet` (balanced)
- `anthropic/claude-haiku` (fast, cheap)
- `meta-llama/llama-3-70b-instruct` (open source)

**Questions:**
- Which models are priority?
- Budget per experiment?
- How to handle model-specific quirks?

### Cost Tracking

**OpenRouter response includes:**
```json
{
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 50,
    "total_tokens": 200
  },
  "model": "openai/gpt-4-turbo",
  // ... model-specific pricing
}
```

**Need to track:**
- Per-question cost
- Per-condition cost
- Per-model cost
- Total experiment cost

**Questions:**
- Cost budget limits?
- Should we cache responses for re-runs?
- Sample subset for testing before full run?

### Function Calling Support

**OpenRouter support:**
- ✅ OpenAI models: Native support
- ✅ Anthropic models: Native support
- ⚠️ Llama 3: Limited/experimental
- ❓ Others: Need to check

**Questions:**
- Should we check function calling support per model?
- Fallback to ReAct for unsupported models?

**Action items:**
- [ ] Choose priority models
- [ ] Test function calling support
- [ ] Set up cost tracking system
- [ ] Implement caching strategy

---

## 5. Evaluation Pipeline

### Input: Questions

From `data/questions/questions_complete.json`:
```json
{
  "id": "A1_001",
  "type": "A1",
  "question": "Which root category does 'rose' belong to?",
  "target": "rose",
  "answer": "floral",
  "distractors": ["fruity", "sweet", "spicy"]
}
```

### Execution Flow

```
For each model in [GPT-4, Claude-Opus, ...]:
    For each condition in [C0, C1, C2, C3, C4, C5]:
        For each question in questions:
            1. Format question for condition
            2. Query LLM via agent
            3. Parse response
            4. Compare with ground truth
            5. Record: correct/incorrect, tokens, cost
            6. Log full trace

Export results:
    - results/model_condition_results.json
    - results/summary_statistics.json
```

### Evaluation Metrics

**Accuracy:**
- Per task type (A1-A5, E1-E3, F)
- Per condition (C0-C5)
- Per model

**Cost:**
- Token count (input + output)
- Dollar cost (via OpenRouter pricing)
- Tool calls (for C3-C4)

**For F-type (open-ended):**
- Use LLM judge (GPT-4 or Claude-Opus)
- Judge prompt: "Is this answer correct given the ground truth?"

**Questions:**
- Run full question set (255 questions) or sample first?
- Parallel execution or sequential?
- How to handle API errors/retries?

**Action items:**
- [ ] Design result schema
- [ ] Implement evaluation loop
- [ ] Design LLM judge for F-type
- [ ] Set up logging and error handling

---

## 6. Configuration Management

### Option A: Python Config Files

```python
# config/experiments.py
EXPERIMENTS = {
    'pilot': {
        'models': ['openai/gpt-3.5-turbo'],
        'conditions': ['C0', 'C3', 'C5'],
        'max_questions': 20,  # Sample
    },
    'full': {
        'models': ['openai/gpt-4', 'anthropic/claude-opus'],
        'conditions': ['C0', 'C1', 'C2', 'C3', 'C4', 'C5'],
        'max_questions': None,  # All
    }
}
```

### Option B: YAML Config

```yaml
# config/experiments.yaml
pilot:
  models:
    - openai/gpt-3.5-turbo
  conditions: [C0, C3, C5]
  max_questions: 20

full:
  models:
    - openai/gpt-4
    - anthropic/claude-opus
  conditions: [C0, C1, C2, C3, C4, C5]
  max_questions: null
```

### Option C: Command-line Arguments

```bash
python scripts/run_evaluation.py \
  --models gpt-4 claude-opus \
  --conditions C0 C3 C5 \
  --questions data/questions/questions_complete.json \
  --output results/experiment_1/
```

**Questions:**
- Which configuration approach?
- How to manage API keys (env variables)?
- How to handle prompt templates?

**Action items:**
- [ ] Choose config approach
- [ ] Design config schema
- [ ] Set up secrets management

---

## 7. Testing Strategy

### Unit Tests

- Test each agent type (C0-C5 handlers)
- Test tool interface
- Test LLM client (with mock)
- Test metrics calculation

### Integration Tests

- Mock LLM client with fixed responses
- Run mini-evaluation (5 questions)
- Verify result format

### Pilot Run

- Use cheap model (GPT-3.5 or Haiku)
- Run 20 sample questions
- Verify everything works end-to-end
- Estimate full run cost

**Action items:**
- [ ] Set up pytest
- [ ] Write unit tests
- [ ] Design integration tests
- [ ] Plan pilot run

---

## 8. Open Questions

### Priority Questions (Must Decide First)

1. **Condition definitions**: What exactly is C0, C1, C2?
2. **Tool interface**: Function calling or ReAct?
3. **Model selection**: Which 2-3 models to start with?
4. **Budget**: What's the cost limit for experiments?

### Secondary Questions (Can Decide During Implementation)

5. Architecture tweaks
6. Config format
7. Logging details
8. Result visualization

---

## 9. Suggested Next Steps

### Phase 1: Design Decisions (This Discussion)
- [ ] Define C0-C5 conditions precisely
- [ ] Choose tool interface approach
- [ ] Select priority models (2-3)
- [ ] Set budget limits

### Phase 2: Core Infrastructure
- [ ] Implement LLM abstract layer (BaseClient, OpenRouterClient)
- [ ] Implement tool interface (GraphTools)
- [ ] Write unit tests

### Phase 3: Agent Implementation
- [ ] Implement C0-C2 agents (direct prompting)
- [ ] Implement C3-C4 agents (tool-augmented)
- [ ] Implement C5 agent (full-context)

### Phase 4: Evaluation Framework
- [ ] Implement evaluation loop
- [ ] Implement metrics calculation
- [ ] Implement result export

### Phase 5: Testing & Pilot
- [ ] Run unit tests
- [ ] Run pilot experiment (20 questions, cheap model)
- [ ] Verify results and costs

### Phase 6: Full Evaluation
- [ ] Run full experiment
- [ ] Generate results (Table 1, Table 2, Figures)
- [ ] Statistical analysis

---

## 10. Discussion Format for Claude Chat

**Suggested prompt for Claude Chat:**

```
I'm building an evaluation framework for tool-augmented LLM reasoning
on coffee flavor hierarchies. I need help making design decisions.

Here's the design document: [paste this file]

Key questions I need help with:
1. How to define experimental conditions C0-C5?
2. Should I use function calling or ReAct for tool interface?
3. Which models should I prioritize for testing?
4. [Any other specific questions]

Can you help me think through these decisions and suggest
best practices for this type of benchmark?
```

---

## Notes

- This is for a research paper, not production deployment
- Focus on reproducibility and clear comparisons
- OpenRouter is chosen for cost efficiency and model variety
- Private data (SYSTEM graph) already handled in previous work
- Question set (255 questions) already generated

---

**Document version**: 1.0
**Date**: 2026-01-29
**Status**: Awaiting design decisions
