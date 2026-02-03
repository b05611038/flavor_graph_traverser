#!/usr/bin/env python3
"""Replace duplicate Brandy with hops"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph

# Load system graph
system_data = load_graph_data('data/graphs/system_graph.pkl')
system_graph = CoffeeDescriptionGraph(
    system_data['descriptions'],
    system_data['connections'],
    root=system_data['root']
)

def get_all_root_categories(graph, descriptor):
    """Get ALL root categories that a descriptor belongs to (DAG-aware)."""
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

# Load questions
with open('data/questions/all_questions_system.json', 'r') as f:
    data = json.load(f)

# Find the duplicate Brandy question to replace
target_id = 'A1_root_classification_rare_003'
target_question = None

for i, q in enumerate(data['questions']):
    if q['id'] == target_id:
        target_question = q
        target_index = i
        break

if not target_question:
    print(f"❌ Question {target_id} not found")
    sys.exit(1)

print(f"Found question to replace:")
print(f"  ID: {target_id}")
print(f"  Old descriptor: {target_question['_objects']['descriptor']}")
print(f"  Old roots: {target_question['_objects']['all_valid_roots']}")
print()

# Get hops info
new_descriptor = 'hops'
valid_roots = get_all_root_categories(system_graph, new_descriptor)

print(f"New descriptor: {new_descriptor}")
print(f"New roots: {valid_roots}")
print()

# Generate new question with hops
random.seed(44)  # Different seed

all_roots = system_graph.get_root_categories()
non_flavor_roots = {'taste', 'defected', 'baked', 'ROOT:SYSTEM'}
all_roots = [r for r in all_roots if r not in non_flavor_roots]

# Generate 5-6 options
num_options = random.choice([5, 6])

# Start with valid roots
options_pool = valid_roots.copy()

# Add random invalid roots
other_roots = [r for r in all_roots if r not in valid_roots]
random.shuffle(other_roots)

while len(options_pool) < num_options and other_roots:
    options_pool.append(other_roots.pop(0))

# Shuffle and assign letters
random.shuffle(options_pool)
options = {chr(65 + i): root for i, root in enumerate(options_pool)}

# Find correct letters
correct_letters = sorted([letter for letter, root in options.items() if root in valid_roots])

# Build question text
question_text = f"Which of the following are root categories that '{new_descriptor}' belongs to? (Select all that apply)"

# Add conditional footnote for 'other'
if 'defected' in options.values():
    question_text += "\n\n*'other' includes non-standard or less common flavor categories"

# Update question
target_question['text'] = question_text
target_question['options'] = options
target_question['correct_answer'] = correct_letters
target_question['_objects']['descriptor'] = new_descriptor
target_question['_objects']['all_valid_roots'] = valid_roots
target_question['_objects']['valid_roots_in_options'] = valid_roots
target_question['_objects']['invalid_roots_in_options'] = [r for r in options_pool if r not in valid_roots]

# Map defected to other
def map_defected_to_other(obj):
    if isinstance(obj, str):
        return obj.replace('defected', 'other')
    elif isinstance(obj, list):
        return [map_defected_to_other(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: map_defected_to_other(v) for k, v in obj.items()}
    else:
        return obj

target_question['text'] = map_defected_to_other(target_question['text'])
target_question['options'] = map_defected_to_other(target_question['options'])
target_question['_objects'] = map_defected_to_other(target_question['_objects'])

# Update in questions list
data['questions'][target_index] = target_question

# Save
print("Saving updated questions...")
with open('data/questions/all_questions_system.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✓ Replaced {target_id}")
print(f"  Old: Brandy (sour/fermented)")
print(f"  New: hops ({', '.join(valid_roots)})")
print()

# Show new question
print("New question preview:")
print(f"  Text: {target_question['text'][:80]}...")
print(f"  Options: {list(target_question['options'].values())}")
print(f"  Correct: {target_question['correct_answer']}")
