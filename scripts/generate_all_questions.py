#!/usr/bin/env python3
"""
Generate All Questions

Generates the full set of ~275 questions across all task types.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.generation import QuestionGenerator


def main():
    print("="*70)
    print("Generate All Questions")
    print("="*70)
    print()

    # Load SYSTEM graph for question generation
    system_graph_file = "data/graphs/system_graph.pkl"
    tool_graph_file = "data/graphs/coffee_flavor_wheel.pkl"

    if not Path(system_graph_file).exists():
        print(f"❌ Graph file not found: {system_graph_file}")
        print()
        print("Please dump graphs first:")
        print("  python scripts/dump_graphs.py")
        return 1

    print(f"Loading SYSTEM graph for questions: {system_graph_file}")
    system_data = load_graph_data(system_graph_file)
    system_graph = CoffeeDescriptionGraph(
        system_data['descriptions'],
        system_data['connections'],
        root=system_data['root']
    )
    print(f"✓ Loaded SYSTEM graph: {len(system_graph.descriptions)} nodes")

    # Load coffee_flavor_wheel graph to create exclusion list
    print(f"Loading tool graph for exclusion: {tool_graph_file}")
    if Path(tool_graph_file).exists():
        tool_data = load_graph_data(tool_graph_file)
        tool_graph = CoffeeDescriptionGraph(
            tool_data['descriptions'],
            tool_data['connections'],
            root=tool_data['root']
        )
        print(f"✓ Loaded tool graph: {len(tool_data['descriptions'])} total nodes")

        # Calculate exclusion list - exclude ALL tool graph nodes (prevent data leakage)
        # Any node in the tool graph can be looked up by a tool-augmented model,
        # so all of them must be excluded from question components.
        all_tool_nodes = set(tool_data['descriptions'])
        # Remove ROOT nodes (structural, not actual flavors)
        tool_nodes_for_exclusion = {n for n in all_tool_nodes if not n.startswith('ROOT:')}
        tool_leaf_nodes = set(tool_graph.get_leaf_nodes())
        tool_non_leaf = all_tool_nodes - tool_leaf_nodes

        print(f"  - Leaf nodes: {len(tool_leaf_nodes)}")
        print(f"  - Non-leaf nodes: {len(tool_non_leaf)} (intermediate/categories)")
        print(f"  - Total tool nodes (excl ROOT): {len(tool_nodes_for_exclusion)} (all excluded)")

        # Add structural/non-flavor categories to exclusion
        print(f"\nExcluding non-flavor categories:")

        # Exclude specific non-flavor categories and their descendants
        non_flavor_descriptors = set()

        # 1. Exclude 'taste' and all its descendants (taste attributes, not flavors)
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
            print(f"  - 'taste' + descendants: {len(taste_descendants)} nodes")

        # 2. Exclude 'baked' (empty category)
        if 'baked' in system_graph.descriptions:
            non_flavor_descriptors.add('baked')
            print(f"  - 'baked': 1 node")

        # 3. Exclude 'defected' root itself (its descendants are valid flavors,
        #    but the root is a category that maps to 'other' in tool graph)
        if 'defected' in system_graph.descriptions:
            non_flavor_descriptors.add('defected')
            print(f"  - 'defected': 1 node (root category, maps to 'other' in tool graph)")

        # 4. Exclude 'ROOT:SYSTEM' node only (not its descendants!)
        if 'ROOT:SYSTEM' in system_graph.descriptions:
            non_flavor_descriptors.add('ROOT:SYSTEM')
            print(f"  - 'ROOT:SYSTEM': 1 node (structural root)")

        # Note: 'defected' (displays as 'other' on wheel) is kept - descendants are valid flavors

        print(f"  Total non-flavor nodes: {len(non_flavor_descriptors)}")

        # Combine exclusions: all tool graph nodes + non-flavor categories
        exclude_set = tool_nodes_for_exclusion | non_flavor_descriptors
        overlap = len(exclude_set & set(system_graph.descriptions))
        available = len(set(system_graph.descriptions) - exclude_set)

        print(f"\n✓ Total exclusions: {len(exclude_set)} nodes")
        print(f"  - Tool graph nodes: {len(tool_nodes_for_exclusion)} (all non-ROOT)")
        print(f"  - Non-flavor categories: {len(non_flavor_descriptors)}")
        print(f"✓ Available: {available} unique flavor descriptors for questions")
        print(f"✓ Design: No question component appears in tool graph")
    else:
        print(f"⚠ Tool graph not found, no exclusion applied")
        exclude_set = set()
        tool_nodes_for_exclusion = set()

    print()

    # Load existing questions (all statuses) to prevent repetition
    existing_questions = []
    master_file = Path("data/questions/all_questions_system.json")
    if master_file.exists():
        with open(master_file) as f:
            existing_data = json.load(f)
        existing_questions = existing_data.get('questions', [])
        print(f"Loaded {len(existing_questions)} existing questions for repetition prevention")
    print()

    # Create generator with exclusion list and tool graph leakage checking
    print("Generating all questions with data leakage prevention...")
    generator = QuestionGenerator(
        system_graph,
        random_seed=42,
        exclude_descriptors=exclude_set,
        tool_graph_nodes=tool_nodes_for_exclusion,
        existing_questions=existing_questions,
    )

    # Generate all questions
    questions = generator.generate_all()

    print(f"✓ Generated {len(questions)} questions")

    # Deduplicate questions by descriptor (important for A1 questions)
    print("\nChecking for duplicate descriptors...")
    unique_questions, duplicates = generator.deduplicate_questions(questions, by_field='descriptor')

    if duplicates:
        print(f"⚠ Found {len(duplicates)} duplicate questions (removed)")
        # Show which descriptors were duplicated
        from collections import Counter
        dup_descriptors = Counter()
        for q in duplicates:
            if '_objects' in q and 'descriptor' in q['_objects']:
                dup_descriptors[q['_objects']['descriptor']] += 1

        print("  Duplicate descriptors:")
        for desc, count in dup_descriptors.most_common(5):
            print(f"    - {desc} (appeared {count + 1} times)")
    else:
        print("✓ No duplicates found")

    questions = unique_questions
    print(f"✓ Final count: {len(questions)} questions")

    print("✓ defected→other mapping and footnote applied inline during generation")
    print()

    # Show breakdown by category
    from collections import Counter
    task_counts = Counter(q['task_type'] for q in questions)

    print("="*70)
    print("Question Breakdown")
    print("="*70)

    print("\nTaxonomic (A1-A5):")
    for task in ['A1_root_classification', 'A2_ancestor_verification',
                 'A3_sibling_identification', 'A4_path_reconstruction',
                 'A5_lca_finding']:
        count = task_counts.get(task, 0)
        print(f"  {task}: {count}")

    print("\nSimilarity (E1-E3):")
    for task in ['E1_similarity_ranking', 'E2_pairwise_comparison',
                 'E3_odd_one_out']:
        count = task_counts.get(task, 0)
        print(f"  {task}: {count}")

    print("\nOpen-ended (F):")
    for task in ['F_flavor_description']:
        count = task_counts.get(task, 0)
        print(f"  {task}: {count}")

    print()
    print(f"Total: {len(questions)} questions")
    print()

    # Save
    output_path = "data/questions/all_questions_system.json"
    generator.save_questions(questions, output_path)
    print(f"✓ Saved to: {output_path}")
    print()
    print("📝 Exclusion Strategy:")
    print("   1. ALL tool graph nodes (prevent data leakage in descriptors, siblings, distractors)")
    print("   2. Non-flavor categories: 'taste', 'baked', 'ROOT:SYSTEM'")
    print("   3. Validator checks ALL question components against tool graph")
    print("   → No question component (descriptor, sibling, distractor) appears in tool graph")
    print("   → LLMs must reason about flavor relationships, not look up answers")
    print()

    # Show some samples
    print("="*70)
    print("Sample Questions")
    print("="*70)

    # Show one from each category
    sample_tasks = [
        'A1_root_classification',
        'A2_ancestor_verification',
        'A3_sibling_identification',
        'A4_path_reconstruction',
        'A5_lca_finding',
        'E1_similarity_ranking',
        'E2_pairwise_comparison',
        'E3_odd_one_out',
        'F_flavor_description'
    ]

    for task_type in sample_tasks:
        matching = [q for q in questions if q['task_type'] == task_type]
        if matching:
            q = matching[0]
            print(f"\n[{q['task_type']}]")
            print(f"  {q['text']}")

            if q.get('options'):
                for k in sorted(q['options'].keys()):
                    if q.get('correct_answer') == k:
                        mark = "✓"
                    else:
                        mark = " "
                    print(f"  [{mark}] ({k}) {q['options'][k]}")

    print()
    print("="*70)
    print("✓ Ready for benchmark evaluation!")
    print("="*70)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
