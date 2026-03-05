# Question Generation

## Overview

Questions are generated from the System Graph using a three-layer pipeline:

```
DescriptorSampler  →  QuestionGenerator  →  QuestionValidator
(exclude leaky nodes)   (build questions)    (reject invalid/leaky)
```

## Quick Start

```bash
# Generate all questions (appends to existing, deduplicates by ID)
python scripts/generate_all_questions.py
```

This automatically:
- Loads all tool graph nodes as the exclusion set
- Skips non-flavor categories (taste, baked)
- Appends new questions to `data/questions/all_questions_system.json`

## Data Leakage Prevention

Any descriptor that appears in the Tool Graph must not appear in generated questions — otherwise a tool-augmented LLM could look it up directly and solve the question mechanically.

The system prevents this at **three layers**:

### Layer 1: Sampler Exclusion
`DescriptorSampler` never samples a node that is in the exclusion set:
```python
sampler = DescriptorSampler(graph, global_exclude=all_tool_nodes)
```

### Layer 2: Validator Rejection
`QuestionValidator` checks every question component against the tool graph and rejects the question if any **protected field** appears there:

**Protected fields** (must NOT be in tool graph):
- `descriptor`, `descriptor1`, `descriptor2`
- `correct_sibling`, `distractor1–3`
- `target`, `option1`, `option2`, `closer`, `farther`, `odd_one`
- Lists: `similar_group`, `candidates`, `all_candidates`

**Structural fields** (allowed in tool graph — these are categories, not specific descriptors):
- `parent`, `ancestor`, `lca`, `root`, `root_category`

### Layer 3: Generation Script
`scripts/generate_all_questions.py` loads **all** tool graph nodes (not just leaves) and passes them to both sampler and validator:
```python
tool_nodes = {n for n in tool_data['descriptions'] if not n.startswith('ROOT:')}
generator = QuestionGenerator(
    system_graph,
    exclude_descriptors=tool_nodes,   # sampler won't pick these
    tool_graph_nodes=tool_nodes        # validator will reject these
)
```

> **Critical rule:** Never create questions manually. Use the generation system, which has all three layers active.

## Graph Filtering

Before generation, the System Graph (1,175 nodes) is filtered to 892 valid nodes using a hierarchical filtering pipeline.

### Filter Configuration

| Parameter | Default | Description |
|---|---|---|
| `require_leaf_node` | `True` | Only leaf nodes (no children) |
| `min_depth` | `2` | Minimum depth from root (excludes root categories themselves) |
| `max_depth` | `None` | No upper limit |
| `excluded_root_categories` | `['taste', 'baked', 'ROOT:SYSTEM']` | Entire branches to exclude |
| `excluded_keywords` | `['ROOT:', 'overall', 'general', 'basic']` | Name patterns to exclude |
| `min_siblings` | `0` | Minimum siblings (set to 2+ for A3 questions) |

### Exception Lists

```bash
# Exclude specific nodes
echo "7up" >> data/filtering/blacklist.txt

# Force-include a filtered-out node
echo "honey" >> data/filtering/whitelist.txt
```

### Filtering Statistics

```
Total:    1,175 nodes
After:      892 nodes (75.9%)

By root (top 5):
  sweet aromatics:  97
  fresh vegetable:  48
  tea-like:         34
  dried fruit:      33
  fruity:           33
```

## Descriptor Sampling Strategies

| Method | Description | Used by |
|---|---|---|
| `sample_leaf()` | Leaf nodes only (no children) | A1, A4 |
| `sample_middle()` | Nodes with both parent and children | A3, E3 |
| `sample_any()` | Any node | A2, A5, E1, E2, F |
| `sample_by_distance()` | Nodes at specific distances from target | E1, E2 |

### E1/E2 Same-Branch Constraint

All candidates in E1/E2 must share the same root category as the target. This avoids ambiguous cross-branch distances (the path through ROOT:SYSTEM has an artificial weight of 10 and doesn't reflect semantic similarity).

```python
# Enabled by default in sample_by_distance()
candidates = sampler.sample_by_distance(target, count=3, same_branch_only=True)
```

## Generation Configuration

Question counts and attempt limits are set in `configs/question_templates.yaml`. Key settings:

```yaml
settings:
  random_seed: 42
  diversity:
    max_descriptor_reuse: 3  # max times a descriptor appears globally (A2, A3, A5, E)

# A1 and A4 allow unlimited descriptor reuse across runs (each question covers a different path)
```

## Validation Checks

Every generated question passes through `QuestionValidator.validate()` which checks:

1. Required fields present (`id`, `category`, `task_type`, `text`, `options`, `correct_answer`)
2. Options format valid (single uppercase letters A–F)
3. Correct answer in options
4. All descriptors exist in System Graph
5. No duplicate options
6. No leakage into Tool Graph (see above)
7. No ROOT:SYSTEM in any field
8. No text overlap between descriptor and options (prevents name-matching shortcuts)
   - E1: reject if correct (closest) candidate shares words with target
   - E2: reject if closer option shares words with target
   - A1–A5: reject if descriptor shares words with any option or parent
   - Exception: A4 (descriptor must appear in the path options)

Task-specific logic for A1 (multi-label root validation) and A2 (ancestor relationship verification) is also enforced.
