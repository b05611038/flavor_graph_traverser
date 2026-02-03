#!/usr/bin/env python3
"""
Generate A1 questions with NONE as correct answer and insert into pending questions.

These questions test whether LLM can correctly identify when no options apply.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import random
from FlavorGraphTraverser.loader import load_graph_data
from FlavorGraphTraverser.graph import CoffeeDescriptionGraph


def generate_none_answer_a1_questions(graph, count=10, random_seed=42):
    """
    Generate A1 questions where correct answer is [] (NONE).

    Strategy: Pick descriptors, show their valid roots, then present 5-6
    options that deliberately EXCLUDE those valid roots.
    """
    random.seed(random_seed)
    questions = []

    # Get all roots
    all_roots = graph.get_root_categories()

    # Filter out non-flavor roots
    non_flavor_roots = {'taste', 'defected', 'baked', 'ROOT:SYSTEM'}
    flavor_roots = [r for r in all_roots if r not in non_flavor_roots]

    # Get leaf descriptors
    leaf_nodes = graph.get_leaf_nodes()

    # Try to generate questions
    attempts = 0
    max_attempts = count * 10

    while len(questions) < count and attempts < max_attempts:
        attempts += 1

        # Sample random leaf descriptor
        descriptor = random.choice(leaf_nodes)

        # Get ALL valid root categories (DAG-aware)
        all_parents = graph.parents_of_description(descriptor)
        valid_roots = set()
        for parent in all_parents:
            try:
                root = graph.get_root_category(parent)
                if root and root in flavor_roots:
                    valid_roots.add(root)
            except:
                pass

        if not valid_roots:
            continue

        valid_roots = sorted(list(valid_roots))

        # Create options that deliberately EXCLUDE valid roots
        invalid_roots = [r for r in flavor_roots if r not in valid_roots]

        if len(invalid_roots) < 5:
            continue  # Need at least 5 invalid options

        # Sample 5-6 invalid roots as options
        num_options = random.choice([5, 6])
        selected_invalid = random.sample(invalid_roots, min(num_options, len(invalid_roots)))

        random.shuffle(selected_invalid)

        # Create options dict
        letters = ['A', 'B', 'C', 'D', 'E', 'F'][:num_options]
        options = {letter: root for letter, root in zip(letters, selected_invalid)}

        # Check if 'defected' in valid roots (will be mapped to 'other')
        has_defected = 'defected' in [r for r in all_roots if r in valid_roots]

        # Format question text
        question_text = f"Which of the following are root categories that '{descriptor}' belongs to? (Select all that apply)"
        if has_defected:
            question_text += "\n\n*'other' includes non-standard or less common flavor categories"

        # Create question
        question = {
            "id": f"A1_root_classification_NONE_{len(questions)+1:03d}",
            "category": "A",
            "task_type": "A1_root_classification",
            "text": question_text,
            "options": options,
            "correct_answer": [],  # NONE - no correct answers
            "answer_format": "multi_label",
            "_template": "Which of the following are root categories that '{descriptor}' belongs to? (Select all that apply)",
            "_objects": {
                "descriptor": descriptor,
                "all_valid_roots": valid_roots,
                "valid_roots_in_options": [],  # None shown
                "invalid_roots_in_options": selected_invalid,
                "none_scenario": True  # Flag for NONE type question
            },
            "_evaluation_note": "NONE scenario: All options are incorrect. Model must select NONE."
        }

        questions.append(question)

    print(f"Generated {len(questions)} NONE-type A1 questions")
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

    # Generate NONE questions
    print("Generating NONE-type A1 questions...")
    none_questions = generate_none_answer_a1_questions(system_graph, count=10, random_seed=42)

    # Apply mapping for 'defected' → 'other'
    print("Applying 'defected' → 'other' mapping...")
    def map_defected_to_other(obj):
        if isinstance(obj, str):
            return obj.replace('defected', 'other')
        elif isinstance(obj, list):
            return [map_defected_to_other(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: map_defected_to_other(v) for k, v in obj.items()}
        else:
            return obj

    for q in none_questions:
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

    print(f"Current questions: {len(data['questions'])}")
    print(f"Reviewed questions: {len(reviewed_ids)}")

    # Separate reviewed and pending A1 questions
    a1_questions = [q for q in data['questions'] if q['task_type'] == 'A1_root_classification']
    other_questions = [q for q in data['questions'] if q['task_type'] != 'A1_root_classification']

    reviewed_a1 = [q for q in a1_questions if q['id'] in reviewed_ids]
    pending_a1 = [q for q in a1_questions if q['id'] not in reviewed_ids]

    print(f"\nA1 questions:")
    print(f"  Reviewed: {len(reviewed_a1)}")
    print(f"  Pending: {len(pending_a1)}")

    # Insert NONE questions randomly into pending A1 questions
    print(f"\nInserting {len(none_questions)} NONE-type questions into pending pool...")
    combined_pending_a1 = pending_a1 + none_questions
    random.seed(42)
    random.shuffle(combined_pending_a1)

    # Reassemble all questions
    all_questions = reviewed_a1 + combined_pending_a1 + other_questions

    # Update metadata
    from collections import Counter
    task_counts = Counter(q['task_type'] for q in all_questions)
    category_counts = Counter(q['category'] for q in all_questions)

    data['metadata']['total_count'] = len(all_questions)
    data['metadata']['by_category'] = dict(category_counts)
    data['metadata']['by_task_type'] = dict(task_counts)
    data['questions'] = all_questions

    # Save
    print(f"\nSaving updated questions...")
    with open(questions_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Complete!")
    print(f"  Total questions: {len(all_questions)}")
    print(f"  A1 questions: {len(reviewed_a1)} reviewed + {len(combined_pending_a1)} pending (includes {len(none_questions)} NONE-type)")
    print(f"  NONE-type questions randomly mixed into pending A1 pool")

    # Show examples
    print("\nExample NONE-type questions:")
    for q in none_questions[:3]:
        print(f"\n  ID: {q['id']}")
        print(f"  Descriptor: {q['_objects']['descriptor']}")
        print(f"  Valid roots (not in options): {q['_objects']['all_valid_roots']}")
        print(f"  Options shown: {list(q['options'].values())}")
        print(f"  Correct answer: {q['correct_answer']} (NONE)")


if __name__ == '__main__':
    main()
