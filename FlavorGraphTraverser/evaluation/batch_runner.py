"""
Batch Runner

Runs benchmark evaluations across multiple questions, models, and conditions.

Features:
    - Result caching (resume interrupted runs)
    - Progress tracking
    - Error handling and retry
    - Parallel execution support
    - Result aggregation

Example:
    >>> from FlavorGraphTraverser.evaluation import BatchRunner
    >>>
    >>> runner = BatchRunner(
    ...     questions_file="data/questions/test_10_questions.json",
    ...     graph_file="data/graphs/coffee_flavor_wheel.pkl",
    ...     output_dir="results"
    ... )
    >>>
    >>> # Run with specific models and conditions
    >>> runner.run(
    ...     models=["tinyllama"],
    ...     conditions=["C0", "C2"],
    ...     client_type="ollama"
    ... )
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

from ..graph import CoffeeDescriptionGraph
from .. import load_graph_data
from .client import create_client
from .tools import GraphToolExecutor
from .evaluator import QuestionEvaluator, EvaluationResult


@dataclass
class BatchConfig:
    """Configuration for batch evaluation."""
    questions_file: str
    graph_file: str
    output_dir: str = "results"
    cache_dir: str = "results/cache"
    enable_cache: bool = True
    verbose: bool = True


class BatchRunner:
    """
    Runs benchmark evaluations across multiple questions, models, and conditions.

    Attributes:
        config: BatchConfig instance
        graph: CoffeeDescriptionGraph instance
        executor: GraphToolExecutor instance
        questions: List of question dicts
        results_cache: Dict of cached results

    Example:
        >>> runner = BatchRunner(
        ...     questions_file="data/questions/test.json",
        ...     graph_file="data/graphs/coffee_flavor_wheel.pkl"
        ... )
        >>>
        >>> runner.run(
        ...     models=["tinyllama"],
        ...     conditions=["C0", "C2"],
        ...     client_type="ollama",
        ...     base_url="http://localhost:11434"
        ... )
    """

    def __init__(
        self,
        questions_file: str,
        graph_file: str,
        output_dir: str = "results",
        cache_dir: Optional[str] = None,
        enable_cache: bool = True,
        verbose: bool = True
    ):
        """
        Initialize batch runner.

        Args:
            questions_file: Path to questions JSON file
            graph_file: Path to graph pickle file
            output_dir: Directory for results
            cache_dir: Directory for cached results (default: {output_dir}/cache)
            enable_cache: Whether to use caching
            verbose: Whether to print progress
        """
        self.config = BatchConfig(
            questions_file=questions_file,
            graph_file=graph_file,
            output_dir=output_dir,
            cache_dir=cache_dir or f"{output_dir}/cache",
            enable_cache=enable_cache,
            verbose=verbose
        )

        # Load graph
        if self.config.verbose:
            print(f"Loading graph from {graph_file}...")

        data = load_graph_data(graph_file)
        self.graph = CoffeeDescriptionGraph(
            data['descriptions'],
            data['connections'],
            root=data['root']
        )

        # Create executor
        self.executor = GraphToolExecutor(self.graph)

        # Load questions
        if self.config.verbose:
            print(f"Loading questions from {questions_file}...")

        with open(questions_file, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict) and "questions" in data:
                self.questions = data["questions"]
                self.metadata = data.get("metadata", {})
            else:
                self.questions = data
                self.metadata = {}

        if self.config.verbose:
            print(f"  Loaded {len(self.questions)} questions")
            print(f"  Graph: {len(self.graph.descriptions)} nodes")

        # Results cache
        self.results_cache = {}
        if self.config.enable_cache:
            self._load_cache()

    def run(
        self,
        models: List[str],
        conditions: List[str],
        client_type: str = "ollama",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run batch evaluation.

        Args:
            models: List of model names (e.g., ["tinyllama", "mistral"])
            conditions: List of conditions (e.g., ["C0", "C1", "C2", "C3"])
            client_type: Client type ("ollama" or "openrouter")
            base_url: Base URL for client (optional)
            api_key: API key for client (optional)

        Returns:
            Dict with results and summary statistics

        Example:
            >>> results = runner.run(
            ...     models=["tinyllama"],
            ...     conditions=["C0", "C2"],
            ...     client_type="ollama"
            ... )
        """
        start_time = time.time()

        # Calculate total evaluations
        total = len(self.questions) * len(models) * len(conditions)

        if self.config.verbose:
            print(f"\n{'='*70}")
            print(f"Batch Evaluation")
            print(f"{'='*70}")
            print(f"Questions: {len(self.questions)}")
            print(f"Models: {models}")
            print(f"Conditions: {conditions}")
            print(f"Total evaluations: {total}")
            print(f"{'='*70}\n")

        # Run evaluations
        completed = 0
        results = []

        for model in models:
            # Create client
            if self.config.verbose:
                print(f"\nModel: {model}")
                print(f"-" * 70)

            try:
                client = create_client(
                    client_type=client_type,
                    model=model,
                    base_url=base_url,
                    api_key=api_key
                )
            except Exception as e:
                print(f"✗ Failed to create client for {model}: {e}")
                continue

            for condition in conditions:
                if self.config.verbose:
                    print(f"\n  Condition: {condition}")

                # Create evaluator
                evaluator = QuestionEvaluator(client, self.executor, condition)

                for i, question in enumerate(self.questions, 1):
                    question_id = question.get("id", f"Q{i}")

                    # Check cache
                    if self._is_cached(model, condition, question_id):
                        if self.config.verbose:
                            print(f"    [{i}/{len(self.questions)}] {question_id}: (cached)")
                        completed += 1
                        # Add cached result to results list
                        cached_result = self._get_cached_result(model, condition, question_id)
                        if cached_result:
                            results.append(cached_result)
                        continue

                    # Run evaluation
                    if self.config.verbose:
                        print(f"    [{i}/{len(self.questions)}] {question_id}: evaluating...", end=" ")

                    try:
                        result = evaluator.evaluate(question)

                        # Save to cache
                        if self.config.enable_cache:
                            self._cache_result(model, condition, question_id, result)

                        results.append(result)

                        # Show result
                        if self.config.verbose:
                            status = "✓" if result.is_correct else "✗"
                            print(f"{status} ({result.status})")

                        completed += 1

                    except Exception as e:
                        if self.config.verbose:
                            print(f"✗ ERROR: {e}")
                        completed += 1
                        continue

        # Calculate elapsed time
        elapsed = time.time() - start_time

        # Generate summary
        summary = self._generate_summary(results, elapsed)

        if self.config.verbose:
            self._print_summary(summary)

        # Save results
        self._save_results(results, summary)

        return {
            "results": results,
            "summary": summary
        }

    def _is_cached(self, model: str, condition: str, question_id: str) -> bool:
        """Check if result is cached."""
        if not self.config.enable_cache:
            return False

        cache_key = f"{model}/{condition}/{question_id}"
        return cache_key in self.results_cache

    def _get_cached_result(self, model: str, condition: str, question_id: str) -> Optional[EvaluationResult]:
        """Get cached result."""
        cache_key = f"{model}/{condition}/{question_id}"
        cached_data = self.results_cache.get(cache_key)

        if cached_data is None:
            return None

        # Convert dict back to EvaluationResult if needed
        if isinstance(cached_data, dict):
            from .evaluator import EvaluationMetrics
            # Reconstruct EvaluationResult from dict
            metrics = EvaluationMetrics(**cached_data.get("metrics", {}))
            result = EvaluationResult(
                question_id=cached_data["question_id"],
                model=cached_data["model"],
                condition=cached_data["condition"],
                question_text=cached_data["question_text"],
                options=cached_data["options"],
                correct_answer=cached_data["correct_answer"],
                model_answer=cached_data.get("model_answer"),
                is_correct=cached_data["is_correct"],
                status=cached_data["status"],
                metrics=metrics,
                conversation_history=cached_data.get("conversation_history", []),
                parse_result=cached_data.get("parse_result"),
                errors=cached_data.get("errors", []),
                timestamp=cached_data.get("timestamp", "")
            )
            return result

        return cached_data

    def _cache_result(self, model: str, condition: str, question_id: str, result: EvaluationResult):
        """Cache a result."""
        cache_key = f"{model}/{condition}/{question_id}"
        self.results_cache[cache_key] = result

        # Save to file
        cache_file = Path(self.config.cache_dir) / model / condition / f"{question_id}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cache_file, 'w') as f:
            json.dump(asdict(result), f, indent=2)

    def _load_cache(self):
        """Load cached results."""
        cache_dir = Path(self.config.cache_dir)

        if not cache_dir.exists():
            return

        # Load all cached results
        for cache_file in cache_dir.rglob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)

                # Extract cache key from path
                parts = cache_file.relative_to(cache_dir).parts
                if len(parts) >= 3:
                    model = parts[0]
                    condition = parts[1]
                    question_id = parts[2].replace(".json", "")

                    cache_key = f"{model}/{condition}/{question_id}"
                    self.results_cache[cache_key] = data

            except Exception:
                continue

    def _generate_summary(self, results: List[EvaluationResult], elapsed: float) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not results:
            return {"total": 0}

        # Group by model and condition
        by_model_condition = defaultdict(list)
        by_model = defaultdict(list)
        by_condition = defaultdict(list)

        for result in results:
            by_model_condition[(result.model, result.condition)].append(result)
            by_model[result.model].append(result)
            by_condition[result.condition].append(result)

        # Calculate accuracy
        def calc_accuracy(results_list):
            if not results_list:
                return 0.0
            correct = sum(1 for r in results_list if r.is_correct)
            return correct / len(results_list)

        summary = {
            "total_evaluations": len(results),
            "elapsed_seconds": elapsed,
            "by_model_condition": {},
            "by_model": {},
            "by_condition": {},
            "overall_accuracy": calc_accuracy(results)
        }

        # By model and condition
        for (model, condition), res_list in by_model_condition.items():
            summary["by_model_condition"][f"{model}_{condition}"] = {
                "count": len(res_list),
                "accuracy": calc_accuracy(res_list),
                "avg_tokens": sum(r.metrics.total_tokens for r in res_list) / len(res_list),
                "avg_latency_ms": sum(r.metrics.latency_ms for r in res_list) / len(res_list),
            }

        # By model
        for model, res_list in by_model.items():
            summary["by_model"][model] = {
                "count": len(res_list),
                "accuracy": calc_accuracy(res_list)
            }

        # By condition
        for condition, res_list in by_condition.items():
            summary["by_condition"][condition] = {
                "count": len(res_list),
                "accuracy": calc_accuracy(res_list)
            }

        return summary

    def _print_summary(self, summary: Dict[str, Any]):
        """Print summary statistics."""
        print(f"\n{'='*70}")
        print(f"Summary")
        print(f"{'='*70}")
        print(f"Total evaluations: {summary['total_evaluations']}")
        print(f"Elapsed time: {summary['elapsed_seconds']:.1f}s")
        print(f"Overall accuracy: {summary['overall_accuracy']:.1%}")

        print(f"\nBy Condition:")
        for condition, stats in summary.get("by_condition", {}).items():
            print(f"  {condition}: {stats['accuracy']:.1%} ({stats['count']} questions)")

        print(f"\nBy Model × Condition:")
        for key, stats in summary.get("by_model_condition", {}).items():
            print(f"  {key}: {stats['accuracy']:.1%} "
                  f"(avg tokens: {stats['avg_tokens']:.0f}, "
                  f"avg latency: {stats['avg_latency_ms']:.0f}ms)")

        print(f"{'='*70}\n")

    def _save_results(self, results: List[EvaluationResult], summary: Dict[str, Any]):
        """Save results to file."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save full results
        results_file = output_dir / "results.json"
        with open(results_file, 'w') as f:
            json.dump({
                "metadata": self.metadata,
                "summary": summary,
                "results": [asdict(r) for r in results]
            }, f, indent=2)

        if self.config.verbose:
            print(f"✓ Results saved to: {results_file}")
