#!/usr/bin/env python3
"""
Run Experiment

Flexible script for running benchmark experiments with configurable parameters.

Usage:
    # Small test (recommended first)
    python scripts/run_experiment.py --models tinyllama --conditions no_tool tool --max-questions 10

    # Full benchmark (all questions, multiple models)
    python scripts/run_experiment.py --models tinyllama mistral --conditions no_tool tool --output results/full_benchmark

    # With OpenRouter
    python scripts/run_experiment.py --client openrouter --models anthropic/claude-sonnet-4.6 --conditions no_tool tool
"""

import sys
import argparse
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser.evaluation import BatchRunner


def main():
    parser = argparse.ArgumentParser(description="Run benchmark experiment")

    parser.add_argument(
        "--questions",
        default="data/questions/benchmark_questions.json",
        help="Path to questions JSON file"
    )

    parser.add_argument(
        "--graph",
        default="data/graphs/coffee_flavor_wheel.pkl",
        help="Path to graph pickle file"
    )

    parser.add_argument(
        "--output",
        default="results/experiment",
        help="Output directory for results"
    )

    parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="Model names (e.g., tinyllama mistral)"
    )

    parser.add_argument(
        "--conditions",
        nargs="+",
        required=True,
        choices=["no_tool", "tool"],
        help="Conditions to test (no_tool=baseline, tool=tool-augmented)"
    )

    parser.add_argument(
        "--client",
        choices=["ollama", "openrouter", "vllm"],
        default="ollama",
        help="Client type"
    )

    parser.add_argument(
        "--base-url",
        help="Base URL for Ollama or vLLM (e.g. http://localhost:8000/v1)"
    )

    parser.add_argument(
        "--api-key",
        help="API key for OpenRouter (default: from environment)"
    )

    parser.add_argument(
        "--max-questions",
        type=int,
        help="Maximum number of questions to evaluate (takes first N)"
    )

    parser.add_argument(
        "--sample",
        type=int,
        metavar="N",
        help="Sample N questions per task type for a representative smoke test"
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching"
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )

    parser.add_argument(
        "--models-config",
        default="configs/models.yaml",
        help="Path to models config YAML (for tool_mode and judge settings)"
    )

    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Disable LLM judge for F-category questions"
    )
    parser.add_argument(
        "--judge-model",
        help="Override judge model ID (default: from models.yaml)"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )

    args = parser.parse_args()

    # Validate files exist
    if not Path(args.questions).exists():
        print(f"❌ Questions file not found: {args.questions}")
        print()
        print("Generate questions first:")
        print("  python scripts/generate_all_questions.py")
        return 1

    if not Path(args.graph).exists():
        print(f"❌ Graph file not found: {args.graph}")
        return 1

    # Load and optionally limit questions
    if args.max_questions:
        import json
        with open(args.questions) as f:
            data = json.load(f)

        limited_questions = data["questions"][:args.max_questions]
        data["questions"] = limited_questions
        data["metadata"]["total_count"] = len(limited_questions)
        data["metadata"]["limited"] = True
        data["metadata"]["original_count"] = len(data["questions"])

        # Save limited questions
        limited_file = f"{args.output}/limited_questions.json"
        Path(limited_file).parent.mkdir(parents=True, exist_ok=True)
        with open(limited_file, 'w') as f:
            json.dump(data, f, indent=2)

        questions_file = limited_file
        print(f"Limited to {args.max_questions} questions")
        print()
    else:
        questions_file = args.questions

    # Print experiment configuration
    print("="*70)
    print("Experiment Configuration")
    print("="*70)
    print(f"Questions: {questions_file}")
    print(f"Graph: {args.graph}")
    print(f"Output: {args.output}")
    print(f"Models: {', '.join(args.models)}")
    print(f"Conditions: {', '.join(args.conditions)}")
    print(f"Client: {args.client}")
    if args.base_url:
        print(f"Base URL: {args.base_url}")
    print(f"Caching: {'disabled' if args.no_cache else 'enabled'}")
    print("="*70)
    print()

    # Calculate expected evaluations
    import json
    with open(questions_file) as f:
        data = json.load(f)
        n_questions = len(data["questions"])

    n_evaluations = n_questions * len(args.models) * len(args.conditions)
    print(f"Expected evaluations: {n_evaluations}")
    print(f"  ({n_questions} questions × {len(args.models)} models × {len(args.conditions)} conditions)")
    print()

    # Estimate time/cost
    if args.client == "ollama":
        est_time_per_eval = 0.5  # seconds
        est_total_time = n_evaluations * est_time_per_eval
        print(f"Estimated time: {est_total_time/60:.1f} minutes")
        print(f"Estimated cost: $0 (local)")
    else:
        est_time_per_eval = 2  # seconds (API latency)
        est_total_time = n_evaluations * est_time_per_eval
        est_cost_per_eval = 0.01  # rough estimate
        est_total_cost = n_evaluations * est_cost_per_eval
        print(f"Estimated time: {est_total_time/60:.1f} minutes")
        print(f"Estimated cost: ${est_total_cost:.2f} (API)")

    # Load models config to extract tool_modes and judge settings
    tool_modes = {}
    judge_model = None
    judge_client_type = None
    if Path(args.models_config).exists():
        with open(args.models_config) as f:
            models_cfg = yaml.safe_load(f)

        # Collect tool_mode overrides (default is "native")
        for section in ("closed_source", "open_source", "local"):
            for entry in models_cfg.get(section, []):
                if entry.get("tool_mode") == "icl":
                    tool_modes[entry["id"]] = "icl"

        # Judge config
        if not args.no_judge:
            judge_cfg = models_cfg.get("judge", {})
            judge_model = args.judge_model or judge_cfg.get("id")
            # Use the same client type as the experiment, or override from config
            judge_client_type = judge_cfg.get("client_type", args.client)

    # CLI --judge-model overrides even if no models.yaml
    if not args.no_judge and args.judge_model and not judge_model:
        judge_model = args.judge_model
        judge_client_type = args.client

    if tool_modes:
        icl_models = [k for k, v in tool_modes.items() if v == "icl"]
        print(f"ICL tool mode: {', '.join(icl_models)}")
    if judge_model:
        print(f"Judge model: {judge_model}")

    print()
    import sys as _sys
    if not args.yes and _sys.stdin.isatty():
        input("Press Enter to continue or Ctrl+C to cancel...")
    print()

    # Create batch runner
    if args.sample:
        print(f"Sample mode: {args.sample} questions per task type")
    runner = BatchRunner(
        questions_file=questions_file,
        graph_file=args.graph,
        output_dir=args.output,
        enable_cache=not args.no_cache,
        verbose=not args.quiet
    )

    # Apply sampling if requested
    if args.sample:
        runner.sample_questions(args.sample)

    # Run experiment
    try:
        results = runner.run(
            models=args.models,
            conditions=args.conditions,
            client_type=args.client,
            base_url=args.base_url,
            api_key=args.api_key,
            judge_model=judge_model,
            judge_client_type=judge_client_type,
            judge_base_url=args.base_url,
            judge_api_key=args.api_key,
            tool_modes=tool_modes or None,
        )

        print()
        print("="*70)
        print("✓ EXPERIMENT COMPLETE")
        print("="*70)
        print()
        print(f"Results saved to: {args.output}/results.json")
        print(f"Cache saved to: {args.output}/cache/")
        print()

        # Print summary
        summary = results["summary"]
        print(f"Total evaluations: {summary['total_evaluations']}")
        print(f"Overall accuracy: {summary['overall_accuracy']:.1%}")
        print(f"Elapsed time: {summary['elapsed_seconds']:.1f}s")
        print()

        print("Next steps:")
        print("  1. Review results in results.json")
        print("  2. Analyze with custom scripts or notebooks")
        print("  3. Generate tables and figures for paper")
        print()

        return 0

    except KeyboardInterrupt:
        print()
        print("="*70)
        print("⚠️  INTERRUPTED")
        print("="*70)
        print()
        print("Experiment interrupted by user.")
        # Mark the last saved results.json as interrupted
        import json as _json
        results_path = Path(args.output) / "results.json"
        if results_path.exists():
            try:
                with open(results_path) as _f:
                    _data = _json.load(_f)
                _data["run_status"] = "interrupted"
                with open(results_path, "w") as _f:
                    _json.dump(_data, _f, indent=2)
                print(f"Partial results marked as interrupted: {results_path}")
            except Exception:
                pass
        print("Re-run the same command to resume from cache.")
        print()
        return 130

    except Exception as e:
        print()
        print("="*70)
        print("❌ ERROR")
        print("="*70)
        print(f"\n{e}\n")

        import traceback
        traceback.print_exc()

        print()
        print("Troubleshooting:")
        if args.client == "ollama":
            print("  - Check Ollama is running: ollama serve")
            print(f"  - Check model is installed: ollama pull {args.models[0]}")
            print("  - Check base URL is correct")
        elif args.client == "vllm":
            print(f"  - Check vLLM server is running at {args.base_url or 'http://localhost:8000/v1'}")
            print(f"  - Check model name matches: curl {args.base_url or 'http://localhost:8000'}/v1/models")
        else:
            print("  - Check API key is set: export OPENROUTER_API_KEY=...")
            print("  - Check model name is correct")
            print("  - Check internet connection")
        print()

        return 1


if __name__ == "__main__":
    sys.exit(main())
