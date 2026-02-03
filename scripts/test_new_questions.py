#!/usr/bin/env python3
"""
Test New Question Types

Quick test to verify all question types work with the evaluator.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.evaluation import BatchRunner


def main():
    print("="*70)
    print("Test New Question Types")
    print("="*70)
    print()
    print("This test runs one question from each type to verify they work.")
    print()

    # Configuration
    questions_file = "data/questions/all_questions.json"
    graph_file = "data/graphs/coffee_flavor_wheel.pkl"
    output_dir = "results/question_type_test"

    # Check files exist
    if not Path(questions_file).exists():
        print(f"❌ Questions file not found: {questions_file}")
        print()
        print("Please generate questions first:")
        print("  python scripts/generate_all_questions.py")
        return 1

    if not Path(graph_file).exists():
        print(f"❌ Graph file not found: {graph_file}")
        return 1

    # Load questions to sample one from each type
    import json
    with open(questions_file) as f:
        data = json.load(f)
        all_questions = data["questions"]

    # Sample one from each task type
    task_types = [
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

    test_questions = []
    for task_type in task_types:
        matching = [q for q in all_questions if q['task_type'] == task_type]
        if matching:
            test_questions.append(matching[0])

    print(f"Selected {len(test_questions)} test questions")
    print()

    # Save test questions to temp file
    test_file = "data/questions/test_question_types.json"
    with open(test_file, 'w') as f:
        json.dump({
            "metadata": {
                "total_count": len(test_questions),
                "description": "One question from each type for testing"
            },
            "questions": test_questions
        }, f, indent=2)

    print(f"Saved test questions to: {test_file}")
    print()

    # Create batch runner
    print("Initializing BatchRunner...")
    print()

    runner = BatchRunner(
        questions_file=test_file,
        graph_file=graph_file,
        output_dir=output_dir,
        enable_cache=True,
        verbose=True
    )

    # Run with TinyLlama, only C0 (zero-shot) to test quickly
    print()
    print("Running evaluation with TinyLlama (C0 only)...")
    print()

    try:
        results = runner.run(
            models=["tinyllama"],
            conditions=["C0"],
            client_type="ollama",
            base_url="http://localhost:11434"
        )

        print()
        print("="*70)
        print("✓ ALL QUESTION TYPES WORK!")
        print("="*70)
        print()
        print(f"Tested {len(test_questions)} question types successfully")
        print(f"Results saved to: {output_dir}/results.json")
        print()

        return 0

    except Exception as e:
        print()
        print("="*70)
        print("❌ ERROR")
        print("="*70)
        print(f"\n{e}\n")

        import traceback
        traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(main())
