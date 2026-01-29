# Filtering Configuration Reference

## Overview

The filtering pipeline (`scripts/flavor_filter.py`) uses a configuration dictionary to control node selection.

---

## Configuration Arguments

### Stage 1: Structural Filters

#### `require_leaf_node` (bool, default: `True`)
- **Description**: Only include leaf nodes (nodes with no children)
- **Purpose**: Target specific flavors, not categories
- **Example**:
  ```python
  'require_leaf_node': True   # Only "rose", not "floral"
  'require_leaf_node': False  # Allow intermediate categories
  ```

#### `min_depth` (int, default: `2`)
- **Description**: Minimum distance from root node
- **Purpose**: Exclude root and top-level categories
- **Example**:
  ```python
  'min_depth': 2  # Exclude root and direct children
  'min_depth': 3  # Only deeply nested nodes
  'min_depth': 1  # Allow top-level categories
  ```
- **Depth levels**:
  - 0: `ROOT:SYSTEM`
  - 1: `floral`, `fruity`, `sweet` (root categories)
  - 2: `red floral`, `white flower` (subcategories)
  - 3+: `rose`, `jasmine` (specific flavors)

#### `max_depth` (int, default: `None`)
- **Description**: Maximum distance from root node
- **Purpose**: Exclude very deep/specific nodes
- **Example**:
  ```python
  'max_depth': None  # No limit
  'max_depth': 4     # Exclude nodes deeper than 4 levels
  ```

#### `require_valid_path` (bool, default: `True`)
- **Description**: Node must have valid path to root
- **Purpose**: Exclude disconnected/orphaned nodes
- **Example**:
  ```python
  'require_valid_path': True   # Must have path to root
  'require_valid_path': False  # Allow orphaned nodes
  ```

---

### Stage 2: Category Filters

#### `excluded_root_categories` (list, default: `['taste', 'defected', 'other']`)
- **Description**: Root categories to exclude
- **Purpose**: Remove problematic category branches entirely
- **Example**:
  ```python
  'excluded_root_categories': [
      'taste',      # Abstract concept
      'defected',   # Quality defects
      'other',      # Catch-all
      'chemical',   # Add more as needed
  ]
  ```
- **Effect**: All descendants of these categories are excluded

#### `excluded_keywords` (list, default: `['ROOT:', 'overall', 'general', 'basic']`)
- **Description**: Keywords that disqualify a node
- **Purpose**: Filter out abstract/meta terms
- **Example**:
  ```python
  'excluded_keywords': [
      'ROOT:',     # System root prefix
      'overall',   # "overall sweet"
      'general',   # Generic terms
      'basic',     # Basic categories
      'sauce',     # Add patterns you find
  ]
  ```
- **Effect**: Node name contains any keyword → excluded

---

### Stage 3: Quality Filters

#### `min_siblings` (int, default: `0`)
- **Description**: Minimum number of siblings required
- **Purpose**: Ensure enough options for A3 (sibling) questions
- **Example**:
  ```python
  'min_siblings': 0  # No requirement
  'min_siblings': 1  # Must have at least 1 sibling
  'min_siblings': 2  # Must have at least 2 siblings
  ```
- **Use case**: Set to 2-3 for generating A3 questions

---

### Stage 4: Exception Lists

#### `manual_blacklist` (set, default: `set()`)
- **Description**: Manually exclude specific nodes
- **Purpose**: Remove problematic nodes you find during review
- **Example**:
  ```python
  'manual_blacklist': {'7up', 'BBQ sauce', 'Yakult'}
  ```
- **Better way**: Use `data/filtering/blacklist.txt` file

#### `manual_whitelist` (set, default: `set()`)
- **Description**: Manually include specific nodes
- **Purpose**: Force include nodes that were filtered out
- **Example**:
  ```python
  'manual_whitelist': {'honey', 'rose hip'}
  ```
- **Better way**: Use `data/filtering/whitelist.txt` file

---

## Default Configuration

```python
default_config = {
    # Stage 1: Structural
    'require_leaf_node': True,
    'min_depth': 2,
    'max_depth': None,
    'require_valid_path': True,

    # Stage 2: Category filtering
    'excluded_root_categories': ['taste', 'defected', 'other'],
    'excluded_keywords': ['ROOT:', 'overall', 'general', 'basic'],

    # Stage 3: Quality
    'min_siblings': 0,

    # Stage 4: Exceptions
    'manual_blacklist': set(),
    'manual_whitelist': set(),
}
```

---

## Usage Examples

### Example 1: Default (Current)
```python
from scripts.flavor_filter import FlavorFilter

filter_obj = FlavorFilter(graph)  # Uses default config
valid_nodes = filter_obj.filter_nodes()
# Result: 892 nodes (75.9%)
```

### Example 2: Stricter Filtering
```python
config = {
    'min_depth': 3,                    # Deeper nodes only
    'min_siblings': 2,                 # Need siblings for A3
    'excluded_root_categories': [
        'taste', 'defected', 'other', 'chemical'
    ],
}
filter_obj = FlavorFilter(graph, config=config)
valid_nodes = filter_obj.filter_nodes()
# Result: ~500-600 nodes (fewer but higher quality)
```

### Example 3: More Relaxed
```python
config = {
    'min_depth': 1,                    # Allow shallow nodes
    'require_leaf_node': False,        # Allow categories
    'excluded_root_categories': [],    # Don't exclude any
}
filter_obj = FlavorFilter(graph, config=config)
valid_nodes = filter_obj.filter_nodes()
# Result: ~1000+ nodes (more variety)
```

### Example 4: Update Existing Config
```python
filter_obj = FlavorFilter(graph)

# Add more excluded categories
filter_obj.update_config(
    excluded_root_categories=['taste', 'defected', 'other', 'chemical']
)

# Add blacklist items
filter_obj.add_to_blacklist(['7up', 'BBQ sauce'])

# Re-filter
valid_nodes = filter_obj.filter_nodes()
```

---

## Tuning Guidelines

### Too Few Nodes (<500)?
1. Reduce `min_depth` from 2 to 1
2. Set `require_leaf_node` to False
3. Reduce `excluded_root_categories` list
4. Remove some `excluded_keywords`

### Too Many Nodes (>1000)?
1. Increase `min_depth` from 2 to 3
2. Add more `excluded_root_categories`
3. Add more `excluded_keywords`
4. Set `min_siblings` to 2-3

### For A3 Questions (Siblings)?
1. Set `min_siblings: 2` (need at least 2 siblings)
2. This ensures enough options for "which shares same parent" questions

### For Quality Control?
1. Review `data/filtering/filtered_nodes_review.json`
2. Add bad nodes to `data/filtering/blacklist.txt`
3. Add good nodes to `data/filtering/whitelist.txt`
4. Re-run filtering

---

## Filtering Statistics

With default config:
- **Total nodes**: 1,175
- **After structural**: 932 (79.3%)
- **After category**: 892 (75.9%)
- **After quality**: 892 (75.9%)
- **Final**: 892 (75.9%)

By root category (top 10):
1. sweet aromatics: 97 nodes
2. fresh vegetable: 48 nodes
3. tea-like: 34 nodes
4. dried fruit: 33 nodes
5. fruity: 33 nodes
6. spices: 25 nodes
7. dried vegetable: 23 nodes
8. jam: 22 nodes
9. brown, roast: 21 nodes
10. grape: 20 nodes

---

## Configuration File Location

- **Code**: `scripts/flavor_filter.py` (line ~25-55)
- **Exception lists**: `data/filtering/blacklist.txt`, `whitelist.txt`
- **Review data**: `data/filtering/filtered_nodes_review.json`

---

## See Also

- `docs/FILTERING_WORKFLOW.md` - Complete workflow guide
- `scripts/review_filtered_nodes.py` - Review tool
- `scripts/flavor_filter.py` - Implementation
