# Flavor Graph Traverser

> Evaluating Tool-Augmented LLMs for Hierarchical Sensory Reasoning

A Python library for representing and traversing coffee flavor hierarchies as directed acyclic graphs (DAGs). This package enables benchmarking of LLM inference on hierarchical reasoning tasks using the coffee flavor wheel taxonomy.

## Research Question

For domain-specific hierarchical reasoning, how does tool-augmented inference compare to direct prompting and full-context approaches?

## Thesis

Tool-augmented LLMs achieve near-full-context accuracy with significantly lower token cost, making them practical for deployable sensory recommendation systems.

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Quick Start

### Basic Graph Operations

```python
from FlavorGraphTraverser import CoffeeDescriptionGraph

# Create a simple flavor graph
descriptions = ['root', 'floral', 'fruity', 'rose', 'jasmine', 'berry', 'citrus']
connections = [
    {'source': 'root', 'target': 'floral', 'path_type': 'sub-category'},
    {'source': 'root', 'target': 'fruity', 'path_type': 'sub-category'},
    {'source': 'floral', 'target': 'rose', 'path_type': 'sub-category'},
    {'source': 'floral', 'target': 'jasmine', 'path_type': 'sub-category'},
    {'source': 'fruity', 'target': 'berry', 'path_type': 'sub-category'},
    {'source': 'fruity', 'target': 'citrus', 'path_type': 'sub-category'},
]

graph = CoffeeDescriptionGraph(descriptions, connections, root='root')

# Query graph structure
print(graph.children_of_description('floral'))
# Output: ['rose', 'jasmine']

print(graph.parents_of_description('rose'))
# Output: ['floral']

# Find paths
paths = graph.pathways_between_descriptions('root', 'rose')
print(paths[0])
# Output: 'root  --[sub-category]->  floral  --[sub-category]->  rose'

# Calculate distances
distance = graph.distance_between_descriptions('rose', 'jasmine')
print(distance)  # Output: 2.0 (rose -> floral -> jasmine)

# Check if graph is valid DAG
print(graph.valid_construction())  # Output: True
```

### Flavor Categories Reference

The package includes the standard 9-category coffee flavor hierarchy:

```python
from FlavorGraphTraverser.flavor_categories import INNER_CATEGORIES, CATEGORY_EXAMPLES

# See all main categories
print(INNER_CATEGORIES)
# ['floral', 'fruity', 'sour/fermented', 'green/vegetable',
#  'defected', 'roasted', 'spices', 'nutty/cocoa', 'sweet']

# See example descriptors for each category
print(CATEGORY_EXAMPLES['floral'])
# ['jasmine', 'rose', 'chamomile', 'lavender', 'tea-like', 'black tea']
```

## Architecture

```
FlavorGraphTraverser/
├── __init__.py              # Main package exports
├── graph.py                 # CoffeeDescriptionGraph - DAG representation
├── utils.py                 # Type validation utilities
├── constants.py             # Default connection weights
└── flavor_categories.py     # Reference flavor hierarchy (9 categories)
```

## Core API: CoffeeDescriptionGraph

Main class for DAG representation of flavor relationships.

### Key Methods

**Graph Queries:**
- `children_of_description(desc)` - Get direct descendants
- `parents_of_description(desc)` - Get direct ancestors
- `get_connection(desc1, desc2)` - Get connection type between nodes

**Path Finding:**
- `pathways_between_descriptions(from, to, k=1)` - Find K shortest paths
- `distance_between_descriptions(from, to)` - Calculate shortest distance

**Graph Analysis:**
- `valid_construction()` - Verify DAG property
- `subgraph_induced_from_description(desc)` - Extract subgraph rooted at node
- `adjacency_matrix()` - Get matrix representation

**Visualization:**
- `plot(filename)` - Save graph visualization

## Use Case: Benchmarking LLM Tool Use

Evaluate whether LLMs can efficiently navigate flavor hierarchies using graph traversal tools instead of requiring full context:

```python
# Expose graph methods as LLM tools
tools = {
    'get_children': graph.children_of_description,
    'get_parents': graph.parents_of_description,
    'find_distance': graph.distance_between_descriptions,
    'find_path': graph.pathways_between_descriptions,
}

# Tool-augmented approach (C3): LLM calls tools to navigate
# Full-context approach (C5): Entire hierarchy in prompt
# Compare accuracy and token efficiency
```

## Benchmark Tasks

**Category A: Taxonomic Reasoning (180 questions)**

- A1: Root classification - "Which root category does 'jasmine' belong to?"
- A2: Ancestor verification - "Is 'rose' a descendant of 'floral'?"
- A3: Sibling identification - "Which shares the same parent as 'jasmine'?"
- A4: Path reconstruction - "What is the path from 'strawberry' to its root?"
- A5: Lowest common ancestor - "Most specific category containing 'jasmine' and 'rose'?"

**Category E: Similarity Reasoning (80 questions)**

- E1: Similarity ranking - "Rank by similarity to 'strawberry': berry, citrus, cocoa"
- E2: Pairwise comparison - "Which is more similar to 'honey': caramel or lemon?"
- E3: Odd one out - "Which does NOT belong: jasmine, rose, chamomile, walnut?"

**Category F: Open Reasoning (15 questions, LLM-judged)**

- "A customer enjoys 'berry' flavors but wants to explore something new. Using the flavor hierarchy, suggest alternatives and explain your reasoning."

See `QUESTIONS.md` for complete task templates.

## Expected Outputs

1. **Table 1: Main Results** - Accuracy (%) by Model × Condition (C0-C5)
2. **Table 2: Per-Task Breakdown** - Accuracy for C0 vs C3 vs C5 across task types
3. **Figure 1: Accuracy vs Tool Calls** - Diminishing returns curve
4. **Figure 2: Token Cost vs Accuracy** - Trade-off scatter plot
5. **Statistical Analysis** - McNemar's test with Bonferroni correction

## Success Criteria

1. Tool-augmented (C3) achieves ≥90% of full-context (C5) accuracy
2. Clear accuracy/cost trade-off curve established
3. Results statistically significant (p < 0.05)
4. Actionable deployment recommendation

## Dependencies

- `numpy>=1.19.0` - Array operations and matrix representations
- `python-igraph>=0.10.0` - Graph data structure and algorithms

## Related Work

Part of the IR-BERT Coffee Chat System project.

## License

MIT License - see LICENSE file for details.

## Citation

```bibtex
@software{flavor_graph_traverser,
  title = {Flavor Graph Traverser: Hierarchical Reasoning Benchmarks for LLMs},
  author = {Your Name},
  year = {2026},
  url = {https://github.com/yourusername/flavor_graph_traverser}
}
```
