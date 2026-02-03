#!/usr/bin/env python3
"""
Add Rare Category A1 Questions

Generate new A1 questions with simple wine-like descriptors
for under-represented categories (sour/fermented, spices).
"""

import sys
import json
import random
from pathlib import Path
from collections import defaultdict

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


def generate_rare_category_a1_questions(system_graph, exclude_set, target_categories, count=7, random_seed=42):
    """Generate A1 questions with simple descriptors for target categories."""
    random.seed(random_seed)

    # Get simple descriptors (single word)
    leaf_nodes = system_graph.get_leaf_nodes()
    simple_descriptors = [desc for desc in leaf_nodes if len(desc.split()) == 1]

    # Filter to available descriptors (not in exclusion set)
    available_descriptors = [desc for desc in simple_descriptors if desc not in exclude_set]

    # Group by root category
    descriptors_by_root = defaultdict(list)
    for desc in available_descriptors:
        valid_roots = get_all_root_categories(system_graph, desc)
        if not valid_roots:
            continue

        for root in valid_roots:
            if root in target_categories:
                descriptors_by_root[root].append({
                    'descriptor': desc,
                    'valid_roots': valid_roots
                })

    print(f"\nAvailable simple descriptors by target category:")
    for cat in target_categories:
        count = len(descriptors_by_root[cat])
        print(f"  {cat}: {count} descriptors")
        if count > 0:
            examples = [d['descriptor'] for d in descriptors_by_root[cat][:5]]
            print(f"    Examples: {', '.join(examples)}")

    # Generate questions
    questions = []
    all_roots = system_graph.get_root_categories()
    non_flavor_roots = {'taste', 'defected', 'baked', 'ROOT:SYSTEM'}
    all_roots = [r for r in all_roots if r not in non_flavor_roots]

    # Track descriptors used
    used_descriptors = set()

    # Try to balance across target categories
    questions_per_category = {}
    for cat in target_categories:
        if cat == 'sour/fermented':
            questions_per_category[cat] = 3  # Need more sour/fermented
        else:
            questions_per_category[cat] = 2  # spices

    for category, target_count in questions_per_category.items():
        available = [d for d in descriptors_by_root[category] if d['descriptor'] not in used_descriptors]

        if len(available) == 0:
            print(f"⚠ No available descriptors for {category}")
            continue

        # Sample up to target_count
        sample_count = min(target_count, len(available))
        sampled = random.sample(available, sample_count)

        for item in sampled:
            descriptor = item['descriptor']
            valid_roots = item['valid_roots']
            used_descriptors.add(descriptor)

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
            question_id = f"A1_root_classification_rare_{len(questions)+1:03d}"
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
    print("Add Rare Category A1 Questions")
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
    print(f"\nTool graph leaf nodes: {len(tool_leaf_nodes)}")

    # Add non-flavor categories
    non_flavor_descriptors = set()

    # Taste + descendants
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
        print(f"Non-flavor nodes (taste+descendants): {len(taste_descendants)}")

    # Baked
    if 'baked' in system_graph.descriptions:
        non_flavor_descriptors.add('baked')

    # ROOT:SYSTEM
    if 'ROOT:SYSTEM' in system_graph.descriptions:
        non_flavor_descriptors.add('ROOT:SYSTEM')

    # Combine exclusions
    exclude_set = tool_leaf_nodes | non_flavor_descriptors
    print(f"Total exclusions: {len(exclude_set)}")

    # Target categories
    target_categories = ['sour/fermented', 'spices']

    # Generate questions
    print(f"\nGenerating A1 questions for: {', '.join(target_categories)}")
    new_questions = generate_rare_category_a1_questions(
        system_graph,
        exclude_set,
        target_categories,
        count=7,
        random_seed=42
    )

    print(f"\n✓ Generated {len(new_questions)} new A1 questions")

    # Load existing questions
    questions_file = "data/questions/all_questions_system.json"
    print(f"\nLoading existing questions: {questions_file}")

    with open(questions_file, 'r') as f:
        data = json.load(f)

    existing_questions = data['questions']
    print(f"Existing questions: {len(existing_questions)}")

    # Separate pending A1 from other questions
    pending_a1 = []
    other_questions = []

    # Load audit state
    audit_state_file = "data/audit_state.json"
    reviewed = set()

    if Path(audit_state_file).exists():
        with open(audit_state_file, 'r') as f:
            audit_state = json.load(f)
            for qid in audit_state.get('confirmed', []):
                reviewed.add(qid)
            for qid in audit_state.get('flagged', []):
                reviewed.add(qid)

    for q in existing_questions:
        if q['task_type'] == 'A1_root_classification' and q['id'] not in reviewed:
            pending_a1.append(q)
        else:
            other_questions.append(q)

    print(f"Pending A1: {len(pending_a1)}")
    print(f"Other questions: {len(other_questions)}")

    # Insert new questions at the FRONT of pending A1
    updated_a1 = new_questions + pending_a1

    # Combine all questions: reviewed + updated_a1 + other tasks
    all_questions = []

    # Add reviewed A1 first
    for q in existing_questions:
        if q['task_type'] == 'A1_root_classification' and q['id'] in reviewed:
            all_questions.append(q)

    # Add updated A1 (new + pending)
    all_questions.extend(updated_a1)

    # Add other task types
    for q in existing_questions:
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
        print(f"  - {q['id']}: {descriptor} ({category})")

    print("\n✓ Done! New rare category questions are at the front of pending A1 queue")


if __name__ == "__main__":
    main()
