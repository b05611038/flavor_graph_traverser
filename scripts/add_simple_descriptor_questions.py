#!/usr/bin/env python3
"""
Generate A1 questions using simple wine-like descriptors for rare categories.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import random
from FlavorGraphTraverser.loader import load_graph_data
from FlavorGraphTraverser.graph import CoffeeDescriptionGraph


def generate_simple_a1_questions(graph, target_categories, count_per_category=3, random_seed=42):
    """
    Generate A1 questions using simple single-word descriptors.

    Args:
        graph: CoffeeDescriptionGraph
        target_categories: List of root categories to focus on
        count_per_category: Number of questions per category
    """
    random.seed(random_seed)
    questions = []

    # Get all leaf nodes
    leaf_nodes = graph.get_leaf_nodes()

    # Filter to simple descriptors (single word)
    simple_descriptors = [desc for desc in leaf_nodes if len(desc.split()) == 1]

    print(f"Found {len(simple_descriptors)} simple descriptors")

    # Get all roots
    all_roots = graph.get_root_categories()
    non_flavor_roots = {'taste', 'defected', 'baked', 'ROOT:SYSTEM'}
    flavor_roots = [r for r in all_roots if r not in non_flavor_roots]

    # Group simple descriptors by root category
    descriptors_by_root = {root: [] for root in flavor_roots}

    for desc in simple_descriptors:
        try:
            # Get all root categories for this descriptor (DAG-aware)
            all_parents = graph.parents_of_description(desc)
            valid_roots = set()
            for parent in all_parents:
                try:
                    root = graph.get_root_category(parent)
                    if root and root in flavor_roots:
                        valid_roots.add(root)
                except:
                    pass

            # Add to each root category it belongs to
            for root in valid_roots:
                descriptors_by_root[root].append({
                    'descriptor': desc,
                    'valid_roots': sorted(list(valid_roots))
                })
        except:
            pass

    print("\nSimple descriptors per category:")
    for root in target_categories:
        print(f"  {root}: {len(descriptors_by_root[root])}")

    # Generate questions for each target category
    question_id_counter = 1

    for root_category in target_categories:
        candidates = descriptors_by_root[root_category]

        if not candidates:
            print(f"Warning: No simple descriptors found for {root_category}")
            continue

        # Shuffle and select
        random.shuffle(candidates)
        selected = candidates[:count_per_category]

        for item in selected:
            descriptor = item['descriptor']
            valid_roots = item['valid_roots']

            # Decide how many options to present (5 or 6)
            num_options = random.choice([5, 6])

            # Decide how many valid roots to include in options
            num_valid_in_options = random.randint(1, min(len(valid_roots), num_options - 2))
            valid_in_options = random.sample(valid_roots, num_valid_in_options)

            # Get invalid roots
            invalid_roots = [r for r in flavor_roots if r not in valid_roots]
            num_invalid_in_options = num_options - num_valid_in_options

            if len(invalid_roots) < num_invalid_in_options:
                continue  # Skip if not enough invalid roots

            invalid_in_options = random.sample(invalid_roots, num_invalid_in_options)

            # Combine and shuffle
            all_options = valid_in_options + invalid_in_options
            random.shuffle(all_options)

            # Create options dict
            letters = ['A', 'B', 'C', 'D', 'E', 'F'][:num_options]
            options = {letter: root for letter, root in zip(letters, all_options)}

            # Find correct letters
            correct_letters = [letter for letter, root in options.items() if root in valid_in_options]
            correct_answer = sorted(correct_letters)

            # Check if 'defected' in valid roots (will be mapped to 'other')
            has_defected = 'defected' in [r for r in all_roots if r in valid_roots]

            # Format question text
            question_text = f"Which of the following are root categories that '{descriptor}' belongs to? (Select all that apply)"
            if has_defected:
                question_text += "\n\n*'other' includes non-standard or less common flavor categories"

            # Create question
            question = {
                "id": f"A1_root_classification_SIMPLE_{question_id_counter:03d}",
                "category": "A",
                "task_type": "A1_root_classification",
                "text": question_text,
                "options": options,
                "correct_answer": correct_answer,
                "answer_format": "multi_label",
                "_template": "Which of the following are root categories that '{descriptor}' belongs to? (Select all that apply)",
                "_objects": {
                    "descriptor": descriptor,
                    "all_valid_roots": valid_roots,
                    "valid_roots_in_options": valid_in_options,
                    "invalid_roots_in_options": invalid_in_options,
                    "simple_descriptor": True
                },
                "_evaluation_note": "Multi-label: Model must select ALL and ONLY the valid roots in options."
            }

            questions.append(question)
            question_id_counter += 1

    print(f"\nGenerated {len(questions)} questions with simple descriptors")
    return questions


def main():
    # Load graph
    print("Loading SYSTEM graph...")
    system_data = load_graph_data('data/graphs/system_graph.pkl')
    system_graph = CoffeeDescriptionGraph(
        system_data['descriptions'],
        system_data['connections'],
        root=system_data['root']
    )

    # Target rare categories
    target_categories = [
        'floral',
        'sour/fermented',
        'nutty/cocoa',
        'spices'
    ]

    # Generate questions
    print("\nGenerating simple descriptor questions for rare categories...")
    simple_questions = generate_simple_a1_questions(
        system_graph,
        target_categories,
        count_per_category=3,
        random_seed=42
    )

    # Apply mapping for 'defected' → 'other'
    print("\nApplying 'defected' → 'other' mapping...")
    def map_defected_to_other(obj):
        if isinstance(obj, str):
            return obj.replace('defected', 'other')
        elif isinstance(obj, list):
            return [map_defected_to_other(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: map_defected_to_other(v) for k, v in obj.items()}
        else:
            return obj

    for q in simple_questions:
        q['text'] = map_defected_to_other(q['text'])
        q['options'] = map_defected_to_other(q['options'])
        if '_objects' in q:
            q['_objects'] = map_defected_to_other(q['_objects'])

    # Load existing questions
    print("\nLoading existing questions...")
    questions_file = 'data/questions/all_questions_system.json'
    with open(questions_file, 'r') as f:
        data = json.load(f)

    # Load audit state
    audit_state_file = 'data/audit_state.json'
    if Path(audit_state_file).exists():
        with open(audit_state_file, 'r') as f:
            audit_state = json.load(f)
    else:
        audit_state = {}

    reviewed_ids = set(audit_state.keys())

    # Separate reviewed and pending
    all_questions = data['questions']
    reviewed = [q for q in all_questions if q['id'] in reviewed_ids]
    pending = [q for q in all_questions if q['id'] not in reviewed_ids]

    print(f"Current: {len(reviewed)} reviewed, {len(pending)} pending")

    # Insert simple questions at the front of pending
    pending_with_simple = simple_questions + pending

    # Reassemble
    all_questions_updated = reviewed + pending_with_simple

    # Update metadata
    from collections import Counter
    task_counts = Counter(q['task_type'] for q in all_questions_updated)
    category_counts = Counter(q['category'] for q in all_questions_updated)

    data['metadata']['total_count'] = len(all_questions_updated)
    data['metadata']['by_category'] = dict(category_counts)
    data['metadata']['by_task_type'] = dict(task_counts)
    data['questions'] = all_questions_updated

    # Save
    print(f"\nSaving updated questions...")
    with open(questions_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Complete!")
    print(f"  Total questions: {len(all_questions_updated)}")
    print(f"  Added {len(simple_questions)} simple descriptor questions at front")
    print(f"  Categories: {target_categories}")

    # Show examples
    print("\nExample simple descriptor questions:")
    for q in simple_questions[:5]:
        desc = q['_objects']['descriptor']
        valid_roots = q['_objects']['all_valid_roots']
        correct = q['correct_answer']
        print(f"  - {desc} (valid: {valid_roots}, answer: {correct})")


if __name__ == '__main__':
    main()
