#!/usr/bin/env python3
"""
Test Evaluator

Demonstrates how to use the QuestionEvaluator to evaluate a single question.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.evaluation import (
    create_client,
    GraphToolExecutor,
    QuestionEvaluator
)


def main():
    print("=" * 70)
    print("QuestionEvaluator Test")
    print("=" * 70)
    print()
    
    # Load graph
    print("Loading coffee_flavor_wheel graph...")
    graph_file = "data/graphs/coffee_flavor_wheel.pkl"
    if not os.path.exists(graph_file):
        print(f"Error: Graph file not found: {graph_file}")
        print("Please run scripts/dump_graphs.py first")
        return
    
    data = load_graph_data(graph_file)
    graph = CoffeeDescriptionGraph(
        data['descriptions'],
        data['connections'],
        root=data['root']
    )
    print(f"  Loaded: {len(graph.descriptions)} nodes")
    print()
    
    # Create executor
    executor = GraphToolExecutor(graph)
    
    # Create example question
    question = {
        "id": "TEST_001",
        "text": "Which root category does 'chocolate' belong to?",
        "options": {
            "A": "fruity",
            "B": "floral", 
            "C": "nutty/cocoa",
            "D": "spices"
        },
        "correct_answer": "C"
    }
    
    print("Test Question:")
    print(f"  {question['text']}")
    print(f"  Options: {question['options']}")
    print(f"  Correct Answer: {question['correct_answer']}")
    print()
    
    # Test with Ollama (local)
    print("Testing with Ollama (TinyLlama)...")
    print("-" * 70)
    
    try:
        client = create_client(
            client_type="ollama",
            model="tinyllama",
            base_url="http://localhost:11434"
        )
        
        if not client.is_available():
            print("  Ollama server not available, skipping...")
        else:
            # Test no_tool (baseline)
            print("\nCondition no_tool (Baseline):")
            evaluator_no_tool = QuestionEvaluator(client, executor, "no_tool")
            result_no_tool = evaluator_no_tool.evaluate(question)

            print(f"  Model Answer: {result_no_tool.model_answer}")
            print(f"  Correct: {result_no_tool.is_correct}")
            print(f"  Status: {result_no_tool.status}")
            print(f"  Tokens: {result_no_tool.metrics.total_tokens}")
            print(f"  Latency: {result_no_tool.metrics.latency_ms}ms")
            print(f"  Parse Pattern: {result_no_tool.parse_result.pattern_matched if result_no_tool.parse_result else 'N/A'}")

            # Test tool (tool-augmented)
            print("\nCondition tool (Tool-Augmented):")
            evaluator_tool = QuestionEvaluator(client, executor, "tool")
            result_tool = evaluator_tool.evaluate(question)

            print(f"  Model Answer: {result_tool.model_answer}")
            print(f"  Correct: {result_tool.is_correct}")
            print(f"  Status: {result_tool.status}")
            print(f"  Reasoning Calls: {result_tool.metrics.reasoning_calls}")
            print(f"  Validation Calls: {result_tool.metrics.validation_calls}")
            print(f"  Total Turns: {result_tool.metrics.total_turns}")
            print(f"  Tokens: {result_tool.metrics.total_tokens}")
            print(f"  Latency: {result_tool.metrics.latency_ms}ms")

            print("\n" + "=" * 70)
            print("Full Result (tool):")
            print("=" * 70)
            
            # Show full result as JSON
            result_dict = {
                "question_id": result_c2.question_id,
                "model": result_c2.model,
                "condition": result_c2.condition,
                "model_answer": result_c2.model_answer,
                "correct_answer": result_c2.correct_answer,
                "is_correct": result_c2.is_correct,
                "status": result_c2.status,
                "metrics": {
                    "reasoning_calls": result_c2.metrics.reasoning_calls,
                    "validation_calls": result_c2.metrics.validation_calls,
                    "total_turns": result_c2.metrics.total_turns,
                    "total_tokens": result_c2.metrics.total_tokens,
                    "latency_ms": result_c2.metrics.latency_ms,
                },
                "errors": result_c2.errors
            }
            
            print(json.dumps(result_dict, indent=2))
            
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 70)
    print("Test complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
