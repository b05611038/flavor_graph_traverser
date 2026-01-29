# Adaptive Filtering Workflow

## Overview

You now have a **hierarchical filtering pipeline** with **exception lists** for adaptive quality control.

## Current Status

✅ **892 valid nodes** (75.9%) filtered from 1,175 total nodes
✅ Multi-stage filtering pipeline
✅ Exception list mechanism ready
✅ Review files generated

---

## Configuration Reference

📖 **See `docs/CONFIG.md` for complete configuration arguments documentation**

**Quick overview of arguments**:
- `min_depth: 2` - Minimum hierarchy depth
- `excluded_root_categories` - Root categories to exclude (default: `['taste', 'defected', 'other']`)
- `excluded_keywords` - Keywords to filter out (default: `['ROOT:', 'overall', 'general', 'basic']`)
- `min_siblings: 0` - Minimum siblings required for A3 questions
- `blacklist.txt` / `whitelist.txt` - Manual exception lists

---

## Workflow

### 1. Review Filtered Nodes

```bash
# From project root directory
cd /path/to/flavor_graph_traverser

# Check the filtered results
cat data/filtering/filtered_nodes_review.json | less

# Or open in editor
code data/filtering/filtered_nodes_review.json  # VSCode
```

**What to look for:**
- Are nodes actual flavors? (e.g., "rose", "chocolate")
- Or are they abstract? (e.g., "taste", "overall sweet")
- Any problematic categories?

### 2. Add Exceptions

**Found problematic nodes?** Add to blacklist:
```bash
# Edit blacklist
echo "7up" >> data/filtering/blacklist.txt
echo "BBQ sauce" >> data/filtering/blacklist.txt
echo "alkali" >> data/filtering/blacklist.txt
```

**Good nodes filtered out?** Add to whitelist:
```bash
# Edit whitelist
echo "honey" >> data/filtering/whitelist.txt
echo "rose hip" >> data/filtering/whitelist.txt
```

### 3. Adjust Parameters (Optional)

Edit `scripts/flavor_filter.py` config (see `docs/CONFIG.md` for details):

```python
def _default_config(self) -> Dict:
    return {
        'min_depth': 3,  # Changed from 2 → require deeper nodes
        'min_siblings': 1,  # Require siblings for A3 questions
        'excluded_root_categories': ['taste', 'defected', 'other', 'chemical'],
        # ... see docs/CONFIG.md for all options
    }
```

Or create custom config in your script:
```python
custom_config = {
    'min_depth': 3,
    'excluded_root_categories': ['taste', 'defected', 'other', 'chemical'],
}
filter_obj = FlavorFilter(graph, config=custom_config)
```

### 4. Re-run Review

```bash
python scripts/review_filtered_nodes.py
```

This will:
- Reload blacklist/whitelist from `data/filtering/`
- Apply filtering again
- Show updated statistics
- Export new review file

### 5. Iterate Until Satisfied

Repeat steps 1-4 until you're happy with the node quality.

---

## Files & Locations

```
Project Structure:
├── scripts/
│   ├── flavor_filter.py           # Filtering implementation
│   ├── review_filtered_nodes.py   # Review tool
│   ├── generate_questions.py      # Question generator
│   └── dump_graphs.py             # Graph extraction
│
├── data/
│   ├── graphs/
│   │   ├── system_graph.pkl              # SYSTEM graph data
│   │   └── coffee_flavor_wheel.pkl       # CFW graph data
│   ├── filtering/
│   │   ├── filtered_nodes_review.json    # For your review
│   │   ├── blacklist.txt                 # Manual exclusions
│   │   └── whitelist.txt                 # Manual inclusions
│   └── questions/
│       └── questions_complete.json       # Generated questions
│
└── docs/
    ├── CONFIG.md                  # ← Configuration reference
    ├── FILTERING_WORKFLOW.md      # ← This file
    ├── QUESTIONS.md               # Question templates
    └── CLAUDE.md                  # Project goals
```

---

## Quality Check Commands

### Show Random Samples by Category
```bash
python scripts/review_filtered_nodes.py --samples
```

### Check Specific Category (Python)
```python
import sys
sys.path.insert(0, 'scripts')
from flavor_filter import FlavorFilter
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph

data = load_graph_data('data/graphs/system_graph.pkl')
graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])

filter_obj = FlavorFilter(graph)
by_cat = filter_obj.get_filtered_by_root_category()

print("Floral nodes:", by_cat.get('floral', []))
```

---

## Your Expert Workflow

As a flavor recognition expert, you can:

1. **Quick Review**: Scan `data/filtering/filtered_nodes_review.json` by category
2. **Spot Issues**: Identify problematic nodes/categories quickly
3. **Add Exceptions**: Update `data/filtering/blacklist.txt` for bad nodes
4. **Iterate Fast**: Re-run and check statistics
5. **Quality Control**: Ensure only actual flavors in questions

The system adapts to your expertise via exception lists!

---

## Example Session

```bash
# 1. Review initial filtering
python scripts/review_filtered_nodes.py
# Output: 892 nodes (75.9%)

# 2. You notice "7up", "BBQ sauce" in sweet aromatics
#    These are not flavors, they are products

# 3. Add to blacklist
echo "7up" >> data/filtering/blacklist.txt
echo "BBQ sauce" >> data/filtering/blacklist.txt
echo "Yakult" >> data/filtering/blacklist.txt

# 4. Also exclude "chemical" category entirely
# Edit scripts/flavor_filter.py:
#   'excluded_root_categories': ['taste', 'defected', 'other', 'chemical']

# 5. Re-run review
python scripts/review_filtered_nodes.py
# Output: 878 nodes (74.7%)

# 6. Check if quality improved
python scripts/review_filtered_nodes.py --samples

# 7. Satisfied? Generate questions
python scripts/generate_questions.py
```

---

## Next Steps

1. ✅ Review `data/filtering/filtered_nodes_review.json`
2. ⏸️ Update `data/filtering/blacklist.txt` / `whitelist.txt` as needed
3. ⏸️ Adjust parameters in `scripts/flavor_filter.py` (see `docs/CONFIG.md`)
4. ⏸️ Re-run `python scripts/review_filtered_nodes.py` to verify
5. ⏸️ Integrate with question generator
6. ⏸️ Generate and review sample questions

---

**Your expertise + adaptive filtering = High-quality question set!** 🎯
