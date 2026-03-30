#!/usr/bin/env python3
"""
Test Full Workflow

End-to-end test of the complete benchmark pipeline:
1. Generate questions
2. Run batch evaluation
3. Check results

Uses TinyLlama on Ollama with 10 test questions.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser.evaluation import BatchRunner


def main():
    print("="*70)
    print("FULL WORKFLOW TEST")
    print("="*70)
    print()
    print("This test runs the complete pipeline:")
    print("  1. Load 10 test questions")
    print("  2. Run batch evaluation with TinyLlama")
    print("  3. Test conditions: no_tool (baseline) and tool (tool-augmented)")
    print("  4. Save and display results")
    print()
    print("="*70)
    print()

    # Configuration
    questions_file = "data/questions/test_10_questions.json"
    graph_file = "data/graphs/coffee_flavor_wheel.pkl"
    output_dir = "results/test_run"

    # Check if questions exist
    if not Path(questions_file).exists():
        print(f"❌ Questions file not found: {questions_file}")
        print()
        print("Please generate questions first:")
        print("  python scripts/generate_test_questions.py")
        return 1

    # Check if graph exists
    if not Path(graph_file).exists():
        print(f"❌ Graph file not found: {graph_file}")
        print()
        print("Please dump graphs first:")
        print("  python scripts/dump_graphs.py")
        return 1

    # Create batch runner
    print("Initializing BatchRunner...")
    print()

    runner = BatchRunner(
        questions_file=questions_file,
        graph_file=graph_file,
        output_dir=output_dir,
        enable_cache=True,
        verbose=True
    )

    # Run batch evaluation
    print()
    print("Starting batch evaluation...")
    print()

    try:
        results = runner.run(
            models=["tinyllama"],
            conditions=["no_tool", "tool"],  # Test both baseline and tool-augmented
            client_type="ollama",
            base_url="http://localhost:11434"  # Default Ollama URL
        )

        print()
        print("="*70)
        print("✓ WORKFLOW TEST COMPLETE")
        print("="*70)
        print()
        print(f"Results saved to: {output_dir}/results.json")
        print(f"Cache saved to: {output_dir}/cache/")
        print()
        print("You can now:")
        print("  1. Review results in results.json")
        print("  2. Re-run to test caching (should skip cached)")
        print("  3. Add more models/conditions")
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

        print()
        print("Common issues:")
        print("  - Ollama not running: Start with 'ollama serve'")
        print("  - TinyLlama not installed: Run 'ollama pull tinyllama'")
        print("  - Wrong Ollama URL: Check base_url parameter")
        print()

        return 1


if __name__ == "__main__":
    sys.exit(main())
