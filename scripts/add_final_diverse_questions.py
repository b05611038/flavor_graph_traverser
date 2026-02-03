#!/usr/bin/env python3
"""
Add Final Diverse A1 Questions

Generate additional A1 questions from under-represented categories
to provide more balanced options for final selection.
"""

import sys
import json
import random
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph


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


def map_defected_to_other(obj):
    """Map 'defected' to 'other' for display."""
    if isinstance(obj, str):
        return obj.replace('defected', 'other')
    elif isinstance(obj, list):
        return [map_defected_to_other(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: map_defected_to_other(v) for k, v in obj.items()}
    else:
        return obj


def generate_diverse_a1_questions(system_graph, exclude_set, used_descriptors,
                                   target_categories, count_per_category, random_seed=42):
    """Generate diverse A1 questions from under-represented categories."""
    random.seed(random_seed)

    # Get leaf descriptors
    leaf_nodes = system_graph.get_leaf_nodes()

    # Group available descriptors by category
    available_by_root = defaultdict(list)

    for desc in leaf_nodes:
        if desc in exclude_set or desc in used_descriptors:
            continue

        valid_roots = get_all_root_categories(system_graph, desc)
        if not valid_roots:
            continue

        for root in valid_roots:
            if root not in ['taste', 'defected', 'baked', 'ROOT:SYSTEM']:
                available_by_root[root].append({
                    'descriptor': desc,
                    'valid_roots': valid_roots
                })

    print(f"\nAvailable descriptors by target category:")
    for cat in target_categories:
        count = len(available_by_root[cat])
        print(f"  {cat}: {count} descriptors")

    # Generate questions
    questions = []
    all_roots = system_graph.get_root_categories()
    non_flavor_roots = {'taste', 'defected', 'baked', 'ROOT:SYSTEM'}
    all_roots = [r for r in all_roots if r not in non_flavor_roots]

    for category, target_count in count_per_category.items():
        available = available_by_root[category]

        if len(available) == 0:
            print(f"⚠ No available descriptors for {category}")
            continue

        # Sample up to target_count
        sample_count = min(target_count, len(available))
        sampled = random.sample(available, sample_count)

        for item in sampled:
            descriptor = item['descriptor']
            valid_roots = item['valid_roots']

            # Generate 5-6 options
            num_options = random.choice([5, 6])

            # Start with valid roots
            options_pool = valid_roots.copy()

            # Add random invalid roots until we have num_options
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
            question_text = f"Which of the following are root categories that '{descriptor}' belongs to? (Select all that apply)"

            # Add conditional footnote for 'other'
            if 'defected' in options.values():
                question_text += "\n\n*'other' includes non-standard or less common flavor categories"

            # Create question
            question_id = f"A1_root_classification_final_{len(questions)+1:03d}"
            question = {
                "id": question_id,
                "category": "A",
                "task_type": "A1_root_classification",
                "text": question_text,
                "options": options,
                "correct_answer": correct_letters,
                "answer_format": "multi_label",
                "_template": "Which of the following are root categories that '{descriptor}' belongs to? (Select all that apply)",
                "_objects": {
                    "descriptor": descriptor,
                    "all_valid_roots": valid_roots,
                    "valid_roots_in_options": valid_roots,
                    "invalid_roots_in_options": [r for r in options_pool if r not in valid_roots],
                    "target_category": category
                }
            }

            # Apply defected → other mapping
            question = map_defected_to_other(question)

            questions.append(question)

    return questions


def main():
    print("="*70)
    print("Add Final Diverse A1 Questions")
    print("="*70)
    print()

    # Load graphs
    system_graph_file = "data/graphs/system_graph.pkl"
    tool_graph_file = "data/graphs/coffee_flavor_wheel.pkl"

    print(f"Loading SYSTEM graph: {system_graph_file}")
    system_data = load_graph_data(system_graph_file)
    system_graph = CoffeeDescriptionGraph(
        system_data['descriptions'],
        system_data['connections'],
        root=system_data['root']
    )
    print(f"✓ Loaded: {len(system_graph.descriptions)} nodes")

    print(f"\nLoading tool graph: {tool_graph_file}")
    tool_data = load_graph_data(tool_graph_file)
    tool_graph = CoffeeDescriptionGraph(
        tool_data['descriptions'],
        tool_data['connections'],
        root=tool_data['root']
    )
    print(f"✓ Loaded: {len(tool_data['descriptions'])} nodes")

    # Build exclusion set
    tool_leaf_nodes = set(tool_graph.get_leaf_nodes())
    non_flavor_descriptors = set()

    if 'taste' in system_graph.descriptions:
        taste_descendants = set(['taste'])
        queue = ['taste']
        visited = set(['taste'])

        while queue:
            node = queue.pop(0)
            children = system_graph.get_children(node)
            for child in children:
                if child not in visited:
                    visited.add(child)
                    taste_descendants.add(child)
                    queue.append(child)

        non_flavor_descriptors.update(taste_descendants)

    if 'baked' in system_graph.descriptions:
        non_flavor_descriptors.add('baked')
    if 'ROOT:SYSTEM' in system_graph.descriptions:
        non_flavor_descriptors.add('ROOT:SYSTEM')

    exclude_set = tool_leaf_nodes | non_flavor_descriptors
    print(f"\nTotal exclusions: {len(exclude_set)}")

    # Load existing questions to get used descriptors
    questions_file = "data/questions/all_questions_system.json"
    with open(questions_file, 'r') as f:
        data = json.load(f)

    used_descriptors = set()
    for q in data['questions']:
        if q['task_type'] == 'A1_root_classification':
            desc = q['_objects'].get('descriptor')
            if desc:
                used_descriptors.add(desc)

    print(f"Used descriptors in existing A1 questions: {len(used_descriptors)}")

    # Target categories - focus on under-represented
    # sour/fermented: 4 (lowest!)
    # nutty/cocoa, floral, spices: 5 each
    count_per_category = {
        'sour/fermented': 3,  # Most needed
        'nutty/cocoa': 2,
        'floral': 2,
        'spices': 1
    }

    print(f"\nGenerating diverse A1 questions...")
    new_questions = generate_diverse_a1_questions(
        system_graph,
        exclude_set,
        used_descriptors,
        list(count_per_category.keys()),
        count_per_category,
        random_seed=43  # Different seed for variety
    )

    print(f"\n✓ Generated {len(new_questions)} new A1 questions")

    # Load audit state
    audit_state_file = "data/audit_state.json"
    reviewed = set()

    if Path(audit_state_file).exists():
        with open(audit_state_file, 'r') as f:
            audit_state = json.load(f)
            for qid, state in audit_state.items():
                if state.get('status') in ['confirmed', 'flagged']:
                    reviewed.add(qid)

    # Separate questions
    pending_a1 = []
    other_questions = []

    for q in data['questions']:
        if q['task_type'] == 'A1_root_classification' and q['id'] not in reviewed:
            pending_a1.append(q)
        else:
            other_questions.append(q)

    print(f"\nExisting pending A1: {len(pending_a1)}")

    # Insert new questions at the FRONT
    updated_a1 = new_questions + pending_a1

    # Combine all questions
    all_questions = []

    # Add reviewed A1 first
    for q in data['questions']:
        if q['task_type'] == 'A1_root_classification' and q['id'] in reviewed:
            all_questions.append(q)

    # Add updated A1 (new + pending)
    all_questions.extend(updated_a1)

    # Add other task types
    for q in data['questions']:
        if q['task_type'] != 'A1_root_classification':
            all_questions.append(q)

    # Update metadata
    by_task_type = defaultdict(int)
    for q in all_questions:
        by_task_type[q['task_type']] += 1

    data['questions'] = all_questions
    data['metadata']['total_count'] = len(all_questions)
    data['metadata']['by_task_type'] = dict(by_task_type)

    # Save
    print(f"\nSaving updated questions: {questions_file}")
    with open(questions_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved {len(all_questions)} questions")
    print(f"\nNew A1 questions added:")
    for q in new_questions:
        descriptor = q['_objects']['descriptor']
        category = q['_objects']['target_category']
        roots = ', '.join(q['_objects']['all_valid_roots'])
        print(f"  - {q['id']}: {descriptor} ({roots})")

    print("\n✓ Done! New diverse questions added to front of pending queue")


if __name__ == "__main__":
    main()
