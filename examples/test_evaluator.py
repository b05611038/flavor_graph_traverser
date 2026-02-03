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
            # Test C0 (zero-shot)
            print("\nCondition C0 (Zero-shot baseline):")
            evaluator_c0 = QuestionEvaluator(client, executor, "C0")
            result_c0 = evaluator_c0.evaluate(question)
            
            print(f"  Model Answer: {result_c0.model_answer}")
            print(f"  Correct: {result_c0.is_correct}")
            print(f"  Status: {result_c0.status}")
            print(f"  Tokens: {result_c0.metrics.total_tokens}")
            print(f"  Latency: {result_c0.metrics.latency_ms}ms")
            print(f"  Parse Pattern: {result_c0.parse_result.pattern_matched if result_c0.parse_result else 'N/A'}")
            
            # Test C2 (tools only)
            print("\nCondition C2 (Tools only):")
            evaluator_c2 = QuestionEvaluator(client, executor, "C2")
            result_c2 = evaluator_c2.evaluate(question)
            
            print(f"  Model Answer: {result_c2.model_answer}")
            print(f"  Correct: {result_c2.is_correct}")
            print(f"  Status: {result_c2.status}")
            print(f"  Reasoning Calls: {result_c2.metrics.reasoning_calls}")
            print(f"  Validation Calls: {result_c2.metrics.validation_calls}")
            print(f"  Total Turns: {result_c2.metrics.total_turns}")
            print(f"  Tokens: {result_c2.metrics.total_tokens}")
            print(f"  Latency: {result_c2.metrics.latency_ms}ms")
            
            print("\n" + "=" * 70)
            print("Full Result (C2):")
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
