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
                all_questions = data["questions"]
                self.metadata = data.get("metadata", {})
            else:
                all_questions = data
                self.metadata = {}

        # Exclude rejected questions
        self.questions = [q for q in all_questions if q.get("status") != "rejected"]
        n_rejected = len(all_questions) - len(self.questions)

        if self.config.verbose:
            print(f"  Loaded {len(self.questions)} questions", end="")
            if n_rejected:
                print(f" ({n_rejected} rejected excluded)", end="")
            print()
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
        api_key: Optional[str] = None,
        judge_model: Optional[str] = None,
        judge_client_type: Optional[str] = None,
        judge_api_key: Optional[str] = None,
        tool_modes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Run batch evaluation.

        Args:
            models: List of model names (e.g., ["tinyllama", "mistral"])
            conditions: List of conditions (e.g., ["C0", "C1", "C2", "C3"])
            client_type: Client type ("ollama" or "openrouter")
            base_url: Base URL for client (optional)
            api_key: API key for client (optional)
            judge_model: Model ID for F-category judge (e.g., "anthropic/claude-opus-4-5").
                         If None, F-category questions are evaluated but not judged.
            judge_client_type: Client type for judge (defaults to client_type if None)
            judge_api_key: API key for judge client (defaults to api_key if None)
            tool_modes: Optional dict mapping model_id -> "native" or "icl".
                        "icl" uses text-based tool simulation for models without
                        native function calling support. Defaults to "native" for
                        any model not listed.

        Returns:
            Dict with results and summary statistics

        Example:
            >>> results = runner.run(
            ...     models=["tinyllama"],
            ...     conditions=["C0", "C2"],
            ...     client_type="ollama",
            ...     judge_model="anthropic/claude-opus-4-5",
            ...     judge_client_type="openrouter",
            ...     judge_api_key=os.getenv("OPENROUTER_API_KEY"),
            ... )
        """
        start_time = time.time()

        # Build judge client (shared across all models/conditions)
        judge_client = None
        if judge_model:
            try:
                judge_client = create_client(
                    client_type=judge_client_type or client_type,
                    model=judge_model,
                    api_key=judge_api_key or api_key,
                )
                if self.config.verbose:
                    print(f"Judge: {judge_model}")
            except Exception as e:
                if self.config.verbose:
                    print(f"⚠ Failed to create judge client: {e}. F-category questions will not be judged.")

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

                # Determine tool mode for this model
                tool_mode = (tool_modes or {}).get(model, "native")

                # Create evaluator (with optional judge for F-category)
                evaluator = QuestionEvaluator(
                    client, self.executor, condition,
                    judge_client=judge_client,
                    tool_mode=tool_mode,
                )

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

                # Incremental save after each model×condition finishes
                elapsed_so_far = time.time() - start_time
                partial_summary = self._generate_summary(results, elapsed_so_far)
                self._save_results(results, partial_summary)
                if self.config.verbose:
                    print(f"  ✓ Checkpoint saved ({len(results)} results so far)")

        # Calculate elapsed time
        elapsed = time.time() - start_time

        # Generate summary
        summary = self._generate_summary(results, elapsed)

        if self.config.verbose:
            self._print_summary(summary)

        # Final save
        self._save_results(results, summary)

        return {
            "results": results,
            "summary": summary
        }

    def sample_questions(self, n_per_type: int) -> None:
        """
        Reduce self.questions to at most n_per_type questions per task_type.
        Picks evenly spaced entries so the sample spans the full list.
        Modifies self.questions in-place.
        """
        from collections import defaultdict
        buckets: Dict[str, list] = defaultdict(list)
        for q in self.questions:
            buckets[q.get("task_type", "unknown")].append(q)

        sampled = []
        for task_type, qs in sorted(buckets.items()):
            if len(qs) <= n_per_type:
                sampled.extend(qs)
            else:
                step = len(qs) / n_per_type
                sampled.extend(qs[int(i * step)] for i in range(n_per_type))

        self.questions = sampled
        if self.config.verbose:
            print(f"  Sampled {len(self.questions)} questions "
                  f"({n_per_type} per task type, {len(buckets)} types)")

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
                timestamp=cached_data.get("timestamp", ""),
                task_type=cached_data.get("task_type", ""),
                model_response_text=cached_data.get("model_response_text"),
                judge_score=cached_data.get("judge_score"),
                judge_result=cached_data.get("judge_result"),
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
        by_task_type = defaultdict(list)

        for result in results:
            by_model_condition[(result.model, result.condition)].append(result)
            by_model[result.model].append(result)
            by_condition[result.condition].append(result)
            if result.task_type:
                by_task_type[result.task_type].append(result)

        # Calculate accuracy
        def calc_accuracy(results_list):
            if not results_list:
                return 0.0
            correct = sum(1 for r in results_list if r.is_correct)
            return correct / len(results_list)

        def calc_avg_judge_score(results_list):
            scored = [r.judge_score for r in results_list if r.judge_score is not None]
            return sum(scored) / len(scored) if scored else None

        summary = {
            "total_evaluations": len(results),
            "elapsed_seconds": elapsed,
            "by_model_condition": {},
            "by_model": {},
            "by_condition": {},
            "by_task_type": {},
            "overall_accuracy": calc_accuracy(results),
        }

        # Separate F-category results for avg score reporting
        f_results = [r for r in results if r.judge_score is not None]
        if f_results:
            summary["f_category_avg_score"] = calc_avg_judge_score(f_results)
            summary["f_category_count"] = len(f_results)

        # By model and condition
        for (model, condition), res_list in by_model_condition.items():
            entry = {
                "count": len(res_list),
                "accuracy": calc_accuracy(res_list),
                "avg_tokens": sum(r.metrics.total_tokens for r in res_list) / len(res_list),
                "avg_latency_ms": sum(r.metrics.latency_ms for r in res_list) / len(res_list),
            }
            avg_score = calc_avg_judge_score(res_list)
            if avg_score is not None:
                entry["f_avg_judge_score"] = avg_score
            summary["by_model_condition"][f"{model}_{condition}"] = entry

        # By model
        for model, res_list in by_model.items():
            entry = {"count": len(res_list), "accuracy": calc_accuracy(res_list)}
            avg_score = calc_avg_judge_score(res_list)
            if avg_score is not None:
                entry["f_avg_judge_score"] = avg_score
            summary["by_model"][model] = entry

        # By condition
        for condition, res_list in by_condition.items():
            entry = {"count": len(res_list), "accuracy": calc_accuracy(res_list)}
            avg_score = calc_avg_judge_score(res_list)
            if avg_score is not None:
                entry["f_avg_judge_score"] = avg_score
            summary["by_condition"][condition] = entry

        # By task type (Table 2 in paper)
        for task_type, res_list in sorted(by_task_type.items()):
            entry = {"count": len(res_list), "accuracy": calc_accuracy(res_list)}
            avg_score = calc_avg_judge_score(res_list)
            if avg_score is not None:
                entry["avg_judge_score"] = avg_score
            summary["by_task_type"][task_type] = entry

        return summary

    def _print_summary(self, summary: Dict[str, Any]):
        """Print summary statistics."""
        print(f"\n{'='*70}")
        print(f"Summary")
        print(f"{'='*70}")
        print(f"Total evaluations: {summary['total_evaluations']}")
        print(f"Elapsed time: {summary['elapsed_seconds']:.1f}s")
        print(f"Overall accuracy: {summary['overall_accuracy']:.1%}")

        if "f_category_avg_score" in summary:
            print(f"F-category avg judge score: {summary['f_category_avg_score']:.2f}/5 "
                  f"({summary['f_category_count']} questions)")

        print(f"\nBy Condition:")
        for condition, stats in summary.get("by_condition", {}).items():
            extra = f" | F avg: {stats['f_avg_judge_score']:.2f}/5" if "f_avg_judge_score" in stats else ""
            print(f"  {condition}: {stats['accuracy']:.1%} ({stats['count']} questions){extra}")

        print(f"\nBy Task Type:")
        for task_type, stats in summary.get("by_task_type", {}).items():
            if "avg_judge_score" in stats:
                extra = f" | avg score: {stats['avg_judge_score']:.2f}/5"
            else:
                extra = ""
            print(f"  {task_type}: {stats['accuracy']:.1%} ({stats['count']} questions){extra}")

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
