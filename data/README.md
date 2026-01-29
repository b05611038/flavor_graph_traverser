# Data Directory

This directory contains data files used for benchmark generation. Real data files are excluded from version control for privacy.

## Directory Structure

```
data/
├── graphs/               # Graph data files
│   ├── example_graph.json          # Example graph structure
│   ├── system_graph.pkl            # [Private] Full SYSTEM graph
│   └── coffee_flavor_wheel.pkl     # [Private] Coffee flavor wheel graph
│
├── filtering/            # Filtering results and configuration
│   ├── example_filtered_nodes.json # Example filtered output
│   ├── example_blacklist.txt       # Example blacklist
│   ├── example_whitelist.txt       # Example whitelist
│   ├── filtered_nodes_review.json  # [Private] Actual filtered nodes
│   ├── blacklist.txt               # [Private] Manual exclusions
│   └── whitelist.txt               # [Private] Manual inclusions
│
└── questions/            # Generated benchmark questions
    ├── example_questions.json      # Example question format
    └── questions_complete.json     # [Private] Full question set
```

## File Formats

### Graph Files (.pkl or .json)

```json
{
  "graph_name": "example_graph",
  "root": "ROOT:EXAMPLE",
  "descriptions": ["ROOT:EXAMPLE", "fruity", "apple"],
  "connections": [
    ["ROOT:EXAMPLE", "fruity"],
    ["fruity", "apple"]
  ]
}
```

### Filtered Nodes Review (.json)

```json
{
  "metadata": {
    "total_nodes": 100,
    "filtered_nodes": 75,
    "percentage": "75.0%",
    "config": {...}
  },
  "nodes_by_category": {
    "fruity": [
      {
        "name": "apple",
        "depth": 2,
        "is_leaf": true,
        "root_category": "fruity",
        "parent": "fruity",
        "siblings": ["pear", "cherry"]
      }
    ]
  }
}
```

### Exception Lists (.txt)

Plain text files with one node name per line:

```
# Comments start with #
problematic_node_1
problematic_node_2
```

### Question Files (.json)

```json
{
  "metadata": {
    "total_questions": 255,
    "graph_source": "system_graph",
    "generation_date": "2024-01-29"
  },
  "questions": [
    {
      "id": "A1_001",
      "type": "A1",
      "category": "taxonomic_reasoning",
      "question": "Which root category does 'rose' belong to?",
      "target": "rose",
      "answer": "floral",
      "distractors": ["fruity", "sweet", "spicy"]
    }
  ]
}
```

## Usage

See `docs/FILTERING_WORKFLOW.md` for complete workflow documentation.

### Load Graph Data

```python
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph

# Load graph
data = load_graph_data('data/graphs/system_graph.pkl')
graph = CoffeeDescriptionGraph(
    data['descriptions'],
    data['connections'],
    root=data['root']
)
```

### Generate Filtered Nodes

```bash
python scripts/review_filtered_nodes.py
```

### Generate Questions

```bash
python scripts/generate_questions.py
```

## Privacy Note

Files marked as **[Private]** contain proprietary data and are excluded from version control. Example files are provided to demonstrate the expected format.
