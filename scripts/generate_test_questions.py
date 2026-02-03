#!/usr/bin/env python3
"""
Generate Test Questions

Generates 10 test questions (5 A1 + 5 A2) for testing the workflow.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.generation import QuestionGenerator
import yaml


def main():
    print("="*70)
    print("Generate Test Questions")
    print("="*70)
    print()

    # Load graph
    graph_file = "data/graphs/coffee_flavor_wheel.pkl"

    if not Path(graph_file).exists():
        print(f"❌ Graph file not found: {graph_file}")
        print()
        print("Please dump graphs first:")
        print("  python scripts/dump_graphs.py")
        return 1

    print(f"Loading graph from {graph_file}...")
    data = load_graph_data(graph_file)
    graph = CoffeeDescriptionGraph(
        data['descriptions'],
        data['connections'],
        root=data['root']
    )
    print(f"✓ Loaded: {len(graph.descriptions)} nodes")
    print()

    # Create generator
    print("Generating questions...")
    generator = QuestionGenerator(graph, random_seed=42)

    # Load config
    config_path = Path("configs/question_templates.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Generate 5 A1 + 5 A2
    config['taxonomic']['A1_root_classification']['count'] = 5
    config['taxonomic']['A2_ancestor_verification']['count'] = 5

    a1 = generator.generate_category(
        "A1_root_classification",
        config['taxonomic']['A1_root_classification']
    )
    a2 = generator.generate_category(
        "A2_ancestor_verification",
        config['taxonomic']['A2_ancestor_verification']
    )

    questions = a1 + a2

    print(f"✓ Generated {len(questions)} questions")
    print(f"  - A1 (Root Classification): {len(a1)}")
    print(f"  - A2 (Ancestor Verification): {len(a2)}")
    print()

    # Save
    output_path = "data/questions/test_10_questions.json"
    generator.save_questions(questions, output_path)
    print(f"✓ Saved to: {output_path}")
    print()

    # Show samples
    print("="*70)
    print("Sample Questions")
    print("="*70)

    for i, q in enumerate([a1[0], a2[0]], 1):
        print(f"\n{i}. [{q['task_type']}]")
        print(f"   {q['text']}")
        for k in sorted(q['options'].keys()):
            mark = "✓" if k == q['correct_answer'] else " "
            print(f"   [{mark}] ({k}) {q['options'][k]}")

    print()
    print("="*70)
    print("✓ Ready for batch evaluation!")
    print("="*70)
    print()
    print("Next step:")
    print("  python scripts/test_full_workflow.py")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
