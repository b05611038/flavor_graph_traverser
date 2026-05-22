#!/usr/bin/env python3
"""
Generate A4 multi-select questions: "Select ALL hierarchies that are fully correct"

Strategy:
1. Each question has 4 options
2. 1-3 are VALID paths (correct parent-child relationships)
3. 1-3 are INVALID paths (fabricated with wrong intermediate nodes)
4. Invalid paths use DISTANT nodes (not siblings/nearby) to avoid confusion
5. Correct answer: list of all valid options (could be [], [A], [A,B], etc.)

Invalid path strategies:
- Wrong root category (e.g., "sweet > ..." for a fruity descriptor)
- Correct root but distant/unrelated intermediate nodes
"""

import sys
import json
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.generation import QuestionValidator


def get_path_to_descriptor(graph, descriptor):
    """Get the full path from root to descriptor."""
    ancestors = graph.get_ancestors(descriptor)
    if not ancestors:
        return None
    return list(reversed(ancestors)) + [descriptor]


def filter_root_system(path):
    """Remove ROOT:SYSTEM from path for display."""
    return [node for node in path if node != 'ROOT:SYSTEM']


def is_leaf_node(graph, node):
    """Check if a node is a leaf (has no children)."""
    children = graph.get_children(node)
    return not children or len(children) == 0


def map_category_for_display(node):
    """Map internal category names to display names."""
    if node == 'defected':
        return 'other'
    return node


def format_path_for_display(path):
    """Format a path with display mapping and > separator."""
    return " > ".join(map_category_for_display(node) for node in path)


def get_all_leaf_paths(graph, tool_leaf_nodes, exclude_roots=None):
    """Get all valid leaf paths."""
    if exclude_roots is None:
        exclude_roots = {'taste', 'baked'}

    leaf_paths = []
    for node in graph.descriptions:
        if node.lower() in tool_leaf_nodes:
            continue
        if node.startswith('ROOT:'):
            continue
        if not is_leaf_node(graph, node):
            continue

        path = get_path_to_descriptor(graph, node)
        if path:
            display_path = filter_root_system(path)
            if display_path and display_path[0] in exclude_roots:
                continue
            if len(display_path) in [3, 4]:
                leaf_paths.append((node, display_path))

    return leaf_paths


def group_paths_by_root(all_paths):
    """Group paths by their root category."""
    by_root = {}
    for descriptor, path in all_paths:
        root = path[0]
        if root not in by_root:
            by_root[root] = []
        by_root[root].append((descriptor, path))
    return by_root


def get_all_non_leaf_nodes_by_root(graph, exclude_roots=None):
    """Get all non-leaf nodes grouped by root for creating invalid paths."""
    if exclude_roots is None:
        exclude_roots = {'taste', 'baked', 'defected'}

    nodes_by_root = {}

    for node in graph.descriptions:
        if node.startswith('ROOT:'):
            continue
        if node in exclude_roots:
            continue
        if is_leaf_node(graph, node):
            continue  # We want intermediate nodes only

        # Get this node's root
        ancestors = graph.get_ancestors(node)
        if ancestors:
            full_path = list(reversed(ancestors))
            roots_in_path = [n for n in full_path if n != 'ROOT:SYSTEM']

            if roots_in_path:
                root = roots_in_path[0]

                if root and root not in exclude_roots:
                    if root not in nodes_by_root:
                        nodes_by_root[root] = []
                    nodes_by_root[root].append(node)

    return nodes_by_root


def create_invalid_path(leaf_descriptor, correct_path, all_paths, intermediate_nodes_by_root):
    """
    Create an invalid path using distant/unrelated nodes.

    Strategies:
    1. Wrong root category (30% chance)
    2. Correct root + wrong distant intermediate nodes (70% chance)
    """
    path_length = len(correct_path)
    correct_root = correct_path[0]

    # Strategy 1: Wrong root category (30% chance)
    if random.random() < 0.3:
        # Pick a different root
        other_roots = [r for r in intermediate_nodes_by_root.keys() if r != correct_root]
        if other_roots:
            wrong_root = random.choice(other_roots)
            # Get intermediate nodes from that root
            intermediate_options = intermediate_nodes_by_root.get(wrong_root, [])

            if intermediate_options:
                # Build path: wrong_root > random intermediates > leaf
                invalid_path = [wrong_root]

                # Add intermediate nodes
                for i in range(path_length - 2):
                    invalid_path.append(random.choice(intermediate_options))

                # End with the leaf (even though it doesn't belong to this root)
                invalid_path.append(leaf_descriptor)

                return invalid_path

    # Strategy 2: Correct root + wrong distant intermediate nodes
    intermediate_options = intermediate_nodes_by_root.get(correct_root, [])

    if not intermediate_options:
        return None

    # Get nodes that are NOT in the correct path (distant nodes)
    distant_nodes = [n for n in intermediate_options if n not in correct_path]

    if len(distant_nodes) < path_length - 2:
        return None

    # Build path: correct_root > wrong intermediates > leaf
    invalid_path = [correct_root]

    # Randomly select distant intermediate nodes
    selected_intermediates = random.sample(distant_nodes, min(len(distant_nodes), path_length - 2))
    invalid_path.extend(selected_intermediates[:path_length - 2])

    # End with the leaf
    invalid_path.append(leaf_descriptor)

    return invalid_path


def generate_multiselect_question(candidate_paths, paths_by_root, intermediate_nodes_by_root, used_descriptors_global):
    """
    Generate one multi-select question with long-tail distribution.

    Distribution of valid answers (0-5):
    - 0 valid: 11% (few NONE)
    - 1 valid: 33% (many)
    - 2 valid: 33% (many)
    - 3 valid: 11% (few)
    - 4 valid: 7%  (few)
    - 5 valid: 4%  (very few ALL)

    Returns: (question_dict, used_descriptors) or (None, set())
    """
    # Long-tail distribution for number of valid paths (0-5)
    # Weighted towards 1-2 correct answers
    distribution = [0]*11 + [1]*33 + [2]*33 + [3]*11 + [4]*7 + [5]*4
    num_valid = random.choice(distribution)
    num_invalid = 5 - num_valid

    # Select valid paths from different roots
    available_roots = list(paths_by_root.keys())
    random.shuffle(available_roots)

    valid_paths = []
    used_local = set()

    for root in available_roots:
        if len(valid_paths) >= num_valid:
            break

        candidates = [(d, p) for d, p in paths_by_root[root]
                      if d not in used_descriptors_global and d not in used_local]

        if candidates:
            selected = random.choice(candidates)
            valid_paths.append(selected)
            used_local.add(selected[0])

    if len(valid_paths) < num_valid:
        return None, set()

    # Create invalid paths
    invalid_paths = []
    attempts = 0
    max_attempts = 50

    while len(invalid_paths) < num_invalid and attempts < max_attempts:
        attempts += 1

        # Pick a random valid path as base
        base_descriptor, base_path = random.choice(candidate_paths)

        # Skip if already used
        if base_descriptor in used_local or base_descriptor in used_descriptors_global:
            continue

        # Create invalid path
        invalid_path = create_invalid_path(
            base_descriptor,
            base_path,
            candidate_paths,
            intermediate_nodes_by_root
        )

        if invalid_path:
            invalid_paths.append((base_descriptor, invalid_path))
            used_local.add(base_descriptor)

    if len(invalid_paths) < num_invalid:
        return None, set()

    # Combine and shuffle
    all_options = []
    correct_letters = []

    for descriptor, path in valid_paths:
        all_options.append(('VALID', descriptor, path))

    for descriptor, path in invalid_paths:
        all_options.append(('INVALID', descriptor, path))

    random.shuffle(all_options)

    # Build question with 5 options (A-E)
    letters = ['A', 'B', 'C', 'D', 'E']
    options = {}

    for i, (status, descriptor, path) in enumerate(all_options):
        letter = letters[i]
        options[letter] = format_path_for_display(path)

        if status == 'VALID':
            correct_letters.append(letter)

    # Sort correct answers for consistency
    correct_letters.sort()

    # Format question text with conditional footnote for 'other'
    question_text = 'Select ALL hierarchies that are fully correct (select all that apply, or none if all are incorrect):'

    # Check if any path contains 'other'
    has_other = any('other' in path_str for path_str in options.values())
    if has_other:
        question_text += "\n\n*'other' includes non-standard or less common flavor categories"

    question = {
        'id': f"A4_multiselect_{random.randint(10000000, 99999999):08x}",
        'category': 'A',
        'task_type': 'A4_path_reconstruction_multiselect',
        'text': question_text,
        'options': options,
        'correct_answer': correct_letters,  # List of letters
        '_template': 'Select ALL hierarchies that are fully correct:',
        '_objects': {
            'num_valid': len(valid_paths),
            'num_invalid': len(invalid_paths),
            'valid_descriptors': [d for d, _ in valid_paths],
            'invalid_descriptors': [d for d, _ in invalid_paths],
            'valid_paths': [p for _, p in valid_paths],
            'invalid_paths': [p for _, p in invalid_paths]
        }
    }

    return question, used_local


def main():
    random.seed(42)

    print("Generating A4 multi-select questions")
    print("=" * 70)

    # Load graphs
    system_data = load_graph_data("data/graphs/system_graph.pkl")
    system_graph = CoffeeDescriptionGraph(
        system_data['descriptions'],
        system_data['connections'],
        root=system_data['root']
    )

    tool_data = load_graph_data("data/graphs/coffee_flavor_wheel.json")
    tool_nodes = {n.lower() for n in tool_data['descriptions'] if not n.startswith('ROOT:')}

    tool_graph = CoffeeDescriptionGraph(
        tool_data['descriptions'],
        tool_data['connections'],
        tool_data['root']
    )
    tool_leaf_nodes = {n.lower() for n in tool_data['descriptions']
                       if is_leaf_node(tool_graph, n) and not n.startswith('ROOT:')}

    print(f"System graph: {len(system_graph.descriptions)} nodes")
    print(f"Tool exclusions: {len(tool_nodes)} nodes")
    print()

    # Get all leaf paths
    all_paths = get_all_leaf_paths(system_graph, tool_leaf_nodes)
    paths_by_root = group_paths_by_root(all_paths)

    # Get intermediate nodes for creating invalid paths
    intermediate_nodes_by_root = get_all_non_leaf_nodes_by_root(system_graph)

    print(f"Found {len(all_paths)} candidate leaf paths")
    print(f"Intermediate nodes by root:")
    for root, nodes in sorted(intermediate_nodes_by_root.items()):
        print(f"  {root}: {len(nodes)} intermediate nodes")
    print()

    # Target: 45 questions
    TARGET_COUNT = 45

    used_descriptors_global = set()
    generated = []
    attempts = 0
    max_attempts = 200

    while len(generated) < TARGET_COUNT and attempts < max_attempts:
        attempts += 1

        question, used_local = generate_multiselect_question(
            all_paths,
            paths_by_root,
            intermediate_nodes_by_root,
            used_descriptors_global
        )

        if question:
            generated.append(question)
            used_descriptors_global.update(used_local)

            num_valid = question['_objects']['num_valid']
            num_invalid = question['_objects']['num_invalid']
            correct = question['correct_answer']

            print(f"{len(generated):3}. Valid={num_valid}, Invalid={num_invalid}, Correct={correct}")

    print()
    print(f"Generated {len(generated)}/{TARGET_COUNT} questions from {attempts} attempts")
    print()

    # Show distributions
    valid_dist = {}
    for q in generated:
        num_valid = q['_objects']['num_valid']
        valid_dist[num_valid] = valid_dist.get(num_valid, 0) + 1

    print("Valid options distribution:")
    for num in sorted(valid_dist.keys()):
        pct = valid_dist[num] / len(generated) * 100
        print(f"  {num} valid: {valid_dist[num]:2} questions ({pct:5.1f}%)")
    print()

    # Save to file
    output_file = "data/questions/a4_multiselect_questions.json"

    output_data = {
        'metadata': {
            'total_questions': len(generated),
            'task_type': 'A4_path_reconstruction_multiselect',
            'generation_method': 'multiselect_with_invalid_paths',
            'question_format': 'Select ALL hierarchies that are fully correct',
            'separator': '>',
            'answer_format': 'list_of_letters',
            'constraints': [
                'Multi-select: 0-4 correct answers per question',
                '1-3 valid paths (correct parent-child relationships)',
                '1-3 invalid paths (wrong intermediate nodes)',
                'Invalid paths use distant/unrelated nodes (not siblings)',
                'Display mapping: defected → other'
            ]
        },
        'questions': generated
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Saved {len(generated)} questions to {output_file}")
    print()

    # Show samples
    if generated:
        print("Sample questions:")
        print()

        for i, q in enumerate(generated[:3], 1):
            print(f"Question {i}:")
            print(f"  {q['text']}")
            print()

            for letter in sorted(q['options'].keys()):
                marker = '✓' if letter in q['correct_answer'] else ' '
                print(f"    {letter}. {q['options'][letter]} {marker}")

            print(f"  Correct answers: {', '.join(q['correct_answer']) if q['correct_answer'] else 'NONE'}")
            print(f"  ({q['_objects']['num_valid']} valid, {q['_objects']['num_invalid']} invalid)")
            print()


if __name__ == "__main__":
    main()
