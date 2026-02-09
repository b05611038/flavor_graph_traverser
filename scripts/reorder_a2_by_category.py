#!/usr/bin/env python3
"""
Reorder A2 questions to prioritize under-represented categories.

Priority order:
1. nutty/cocoa (rarest - only 2 descriptors)
2. floral, spices (5 each)
3. sour/fermented (8)
4. defected (6)
5. green/vegetable, roasted (13 each)
6. fruity, sweet (most common - 21 each)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph


def get_root_categories(graph, descriptor):
    """Get all root categories for a descriptor."""
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


def main():
    print("="*70)
    print("Reorder A2 Questions by Category Priority")
    print("="*70)
    print()

    # Load system graph
    system_data = load_graph_data('data/graphs/system_graph.pkl')
    system_graph = CoffeeDescriptionGraph(
        system_data['descriptions'],
        system_data['connections'],
        root=system_data['root']
    )

    # Load questions
    with open('data/questions/all_questions_system.json', 'r') as f:
        data = json.load(f)

    # Separate A2 from other questions
    a2_questions = []
    other_questions = []

    for q in data['questions']:
        if q['task_type'] == 'A2_ancestor_verification':
            a2_questions.append(q)
        else:
            other_questions.append(q)

    print(f"Found {len(a2_questions)} A2 questions to reorder")
    print()

    # Define priority scores (lower = higher priority)
    priority_scores = {
        'nutty/cocoa': 1,      # Rarest
        'floral': 2,
        'spices': 2,
        'defected': 3,
        'sour/fermented': 4,
        'green/vegetable': 5,
        'roasted': 5,
        'fruity': 6,           # Most common
        'sweet': 6
    }

    # Score each A2 question
    scored_questions = []

    for q in a2_questions:
        desc = q['_objects']['descriptor']

        try:
            roots = get_root_categories(system_graph, desc)

            # Use minimum priority (highest priority category)
            if roots:
                min_priority = min(priority_scores.get(r, 10) for r in roots)
            else:
                min_priority = 10

            scored_questions.append((min_priority, q))
        except:
            scored_questions.append((10, q))

    # Sort by priority (lower first), then by ID for stability
    scored_questions.sort(key=lambda x: (x[0], x[1]['id']))

    # Extract sorted questions
    sorted_a2 = [q for _, q in scored_questions]

    print("Priority distribution after reordering:")
    from collections import Counter
    priority_counts = Counter(score for score, _ in scored_questions)
    for priority in sorted(priority_counts.keys()):
        count = priority_counts[priority]
        if priority == 1:
            label = "nutty/cocoa"
        elif priority == 2:
            label = "floral, spices"
        elif priority == 3:
            label = "defected"
        elif priority == 4:
            label = "sour/fermented"
        elif priority == 5:
            label = "green/vegetable, roasted"
        elif priority == 6:
            label = "fruity, sweet"
        else:
            label = "unknown"
        print(f"  Priority {priority} ({label}): {count} questions")

    print()

    # Show first 10 questions after reordering
    print("First 10 questions after reordering:")
    for i, q in enumerate(sorted_a2[:10], 1):
        desc = q['_objects']['descriptor']
        try:
            roots = get_root_categories(system_graph, desc)
            print(f"  {i}. {desc} ({' + '.join(roots)})")
        except:
            print(f"  {i}. {desc}")

    print()

    # Reconstruct full question list
    # Keep other question types in their original positions
    all_questions = other_questions + sorted_a2

    # Update metadata
    data['questions'] = all_questions

    # Save
    output_file = 'data/questions/all_questions_system.json'
    print(f"Saving reordered questions to: {output_file}")

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("✓ Done!")
    print()
    print("Rare categories (nutty/cocoa, floral, spices) now appear first")
    print("in the audit queue.")


if __name__ == "__main__":
    main()
