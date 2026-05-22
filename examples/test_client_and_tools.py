#!/usr/bin/env python3
"""
Test Client and Tools Integration

Demonstrates how to use the LLM client and graph tools together.
Tests both Ollama (local) and OpenRouter (API) clients.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.evaluation.client import create_client, Message
from FlavorGraphTraverser.evaluation.tools import GraphToolExecutor, get_tool_definitions


def test_ollama_client():
    """Test Ollama client connectivity."""
    print("=" * 60)
    print("Testing Ollama Client")
    print("=" * 60)
    
    try:
        client = create_client(
            client_type="ollama",
            model="tinyllama",
            base_url="http://localhost:11434"
        )
        
        # Check availability
        print(f"Ollama available: {client.is_available()}")
        
        if client.is_available():
            # List models
            models = client.list_models()
            print(f"Available models: {models}")
            
            # Simple query
            messages = [Message(role="user", content="What is 2+2? Answer briefly.")]
            response = client.query(messages, temperature=0, max_tokens=100)
            
            print(f"\nQuery: What is 2+2?")
            print(f"Response: {response.content}")
            print(f"Tokens: {response.usage}")
        else:
            print("Ollama server not available at http://localhost:11434")
            
    except Exception as e:
        print(f"Error: {e}")
    
    print()


def test_graph_tools():
    """Test graph tool executor."""
    print("=" * 60)
    print("Testing Graph Tools")
    print("=" * 60)
    
    try:
        # Load coffee_flavor_wheel graph
        graph_file = "data/graphs/coffee_flavor_wheel.json"
        
        if not os.path.exists(graph_file):
            print(f"Graph file not found: {graph_file}")
            print("Please run scripts/dump_graphs.py first")
            return
        
        data = load_graph_data(graph_file)
        graph = CoffeeDescriptionGraph(
            data['descriptions'],
            data['connections'],
            root=data['root']
        )
        
        print(f"Loaded graph: {data['graph_name']}")
        print(f"Nodes: {len(graph.descriptions)}")
        print()
        
        # Create executor
        executor = GraphToolExecutor(graph)
        
        # Test validate_descriptors
        print("Test 1: validate_descriptors")
        result = executor.validate_descriptors(['fruity', 'floral', 'chocolate', 'unknown', 'rose'])
        print(f"  Input: ['fruity', 'floral', 'chocolate', 'unknown', 'rose']")
        print(f"  Valid: {result['valid']}")
        print(f"  Invalid: {result['invalid']}")
        print()
        
        # Test get_parent
        print("Test 2: get_parent")
        if 'rose' in graph.descriptions:
            result = executor.get_parent('rose')
            print(f"  get_parent('rose')")
            print(f"  Parents: {result['parents']}")
            print(f"  Error: {result['error']}")
        print()
        
        # Test get_children
        print("Test 3: get_children")
        if 'berry' in graph.descriptions:
            result = executor.get_children('berry')
            print(f"  get_children('berry')")
            print(f"  Children: {result['children']}")
            print(f"  Error: {result['error']}")
        print()
        
        # Test error handling
        print("Test 4: Error handling (invalid descriptor)")
        result = executor.get_parent('invalid_node')
        print(f"  get_parent('invalid_node')")
        print(f"  Parents: {result['parents']}")
        print(f"  Error: {result['error']}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()


def test_tool_definitions():
    """Test tool definition generation."""
    print("=" * 60)
    print("Testing Tool Definitions")
    print("=" * 60)
    
    tools = get_tool_definitions()
    print(f"Total tools: {len(tools)}")
    
    for tool in tools:
        func = tool['function']
        print(f"\nTool: {func['name']}")
        print(f"  Description: {func['description'][:80]}...")
        print(f"  Parameters: {list(func['parameters']['properties'].keys())}")
    
    print()


if __name__ == "__main__":
    print("\nFlavorGraphTraverser - Client & Tools Test\n")
    
    # Run tests
    test_tool_definitions()
    test_graph_tools()
    test_ollama_client()
    
    print("=" * 60)
    print("Tests complete!")
    print("=" * 60)
