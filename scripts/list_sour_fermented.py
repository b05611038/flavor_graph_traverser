#!/usr/bin/env python3
"""List all available sour/fermented descriptors"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph

# Load graphs
system_data = load_graph_data('data/graphs/system_graph.pkl')
system_graph = CoffeeDescriptionGraph(
    system_data['descriptions'],
    system_data['connections'],
    root=system_data['root']
)

tool_data = load_graph_data('data/graphs/coffee_flavor_wheel.pkl')
tool_graph = CoffeeDescriptionGraph(
    tool_data['descriptions'],
    tool_data['connections'],
    root=tool_data['root']
)

# Build exclusion set
tool_leaf_nodes = set(tool_graph.get_leaf_nodes())
non_flavor = set()

if 'taste' in system_graph.descriptions:
    queue = ['taste']
    visited = set(['taste'])
    while queue:
        node = queue.pop(0)
        children = system_graph.get_children(node)
        for child in children:
            if child not in visited:
                visited.add(child)
                non_flavor.add(child)
                queue.append(child)
    non_flavor.add('taste')

if 'baked' in system_graph.descriptions:
    non_flavor.add('baked')
if 'ROOT:SYSTEM' in system_graph.descriptions:
    non_flavor.add('ROOT:SYSTEM')

exclude_set = tool_leaf_nodes | non_flavor

# Load confirmed A1 descriptors
with open('data/questions/all_questions_system.json', 'r') as f:
    data = json.load(f)

with open('data/audit_state.json', 'r') as f:
    audit_state = json.load(f)

confirmed_descriptors = set()
for qid, state in audit_state.items():
    if state.get('status') == 'confirmed' and qid.startswith('A1_root'):
        q = next((q for q in data['questions'] if q['id'] == qid), None)
        if q:
            confirmed_descriptors.add(q['_objects']['descriptor'])

# Get all root categories helper
def get_all_root_categories(graph, descriptor):
    all_parents = graph.parents_of_description(descriptor)
    root_categories = set()
    for parent in all_parents:
        try:
            root = graph.get_root_category(parent)
            if root:
                root_categories.add(root)
        except:
            pass
    return sorted(list(root_categories))

# Find available sour/fermented descriptors
leaf_nodes = system_graph.get_leaf_nodes()
sour_fermented_descriptors = []

for desc in leaf_nodes:
    # Skip if excluded or already used
    if desc in exclude_set or desc in confirmed_descriptors:
        continue

    valid_roots = get_all_root_categories(system_graph, desc)

    # Check if it has sour/fermented as one of its roots
    if 'sour/fermented' in valid_roots:
        sour_fermented_descriptors.append({
            'descriptor': desc,
            'roots': valid_roots
        })

# Sort by number of roots (prefer single-root first, then multi-root)
sour_fermented_descriptors.sort(key=lambda x: (len(x['roots']), x['descriptor']))

print('='*70)
print(f'Available sour/fermented descriptors: {len(sour_fermented_descriptors)}')
print('='*70)
print()

# Categorize by number of roots
single_root = [d for d in sour_fermented_descriptors if len(d['roots']) == 1]
multi_root = [d for d in sour_fermented_descriptors if len(d['roots']) > 1]

print(f'Single-root (sour/fermented only): {len(single_root)}')
print('-'*70)
for i, item in enumerate(single_root, 1):
    desc = item['descriptor']
    # Highlight simple (single word) descriptors
    marker = '⭐' if len(desc.split()) == 1 else '  '
    print(f'{marker} {i:2d}. {desc}')

print()
print(f'Multi-root (sour/fermented + others): {len(multi_root)}')
print('-'*70)
for i, item in enumerate(multi_root, 1):
    desc = item['descriptor']
    other_roots = [r for r in item['roots'] if r != 'sour/fermented']
    marker = '⭐' if len(desc.split()) == 1 else '  '
    print(f'{marker} {i:2d}. {desc} (+ {" + ".join(other_roots)})')

print()
print('='*70)
print('Legend: ⭐ = Simple (single word) descriptor')
print(f'Note: Excluded {len(confirmed_descriptors)} already confirmed descriptors')
