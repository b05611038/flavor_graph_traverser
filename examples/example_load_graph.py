#!/usr/bin/env python3
"""
Example: Loading and Using Pre-packed Graph
============================================

This script demonstrates how to load and use the packed SYSTEM graph.

Prerequisites:
    1. Run extract_system_graph.py first to create the data files
    2. Ensure system_graph_data.json or system_graph_data.pkl exists

Usage:
    python example_load_graph.py
"""

from FlavorGraphTraverser import load_system_graph


def main():
    print("=" * 70)
    print("Loading Pre-packed SYSTEM Graph")
    print("=" * 70)

    # Load the graph
    print("\n1. Loading graph from packed data...")
    try:
        graph = load_system_graph()
        print(f"   ✓ Loaded graph: {graph.graph_name}")
        print(f"   ✓ Total descriptions: {len(graph.descriptions)}")
    except FileNotFoundError as e:
        print(f"\n   ✗ Error: {e}")
        print("\n   Please run 'python extract_system_graph.py' first!")
        return 1

    # Basic information
    print("\n2. Graph Information:")
    print(f"   Root: {graph.root}")
    print(f"   Is valid DAG: {graph.valid_construction()}")

    # Show first few descriptions
    print(f"\n3. First 10 descriptions:")
    for i, desc in enumerate(graph.descriptions[:10], 1):
        print(f"   {i:2d}. {desc}")
    print(f"   ... and {len(graph.descriptions) - 10} more")

    # Example 1: Get children
    print("\n" + "=" * 70)
    print("Example 1: Get Children of Description")
    print("=" * 70)

    test_descriptions = ['floral', 'fruity', 'sweet']
    for desc in test_descriptions:
        if desc in graph.descriptions:
            children = graph.children_of_description(desc)
            print(f"\n   '{desc}' has {len(children)} children:")
            for child in children[:5]:  # Show first 5
                print(f"     - {child}")
            if len(children) > 5:
                print(f"     ... and {len(children) - 5} more")
        else:
            print(f"\n   '{desc}' not found in graph")

    # Example 2: Get parents
    print("\n" + "=" * 70)
    print("Example 2: Get Parents of Description")
    print("=" * 70)

    test_leaf = next((d for d in graph.descriptions if 'rose' in d.lower()), None)
    if test_leaf:
        parents = graph.parents_of_description(test_leaf)
        print(f"\n   '{test_leaf}' has {len(parents)} parent(s):")
        for parent in parents:
            print(f"     - {parent}")
    else:
        print("\n   No suitable leaf node found for example")

    # Example 3: Find paths
    print("\n" + "=" * 70)
    print("Example 3: Find Paths Between Descriptions")
    print("=" * 70)

    # Find two descriptions with a path
    from_desc = graph.root
    to_desc = None

    # Find a leaf node
    for desc in graph.descriptions:
        if len(graph.children_of_description(desc)) == 0:
            to_desc = desc
            break

    if from_desc and to_desc:
        print(f"\n   Finding path from '{from_desc}' to '{to_desc}':")

        paths = graph.pathways_between_descriptions(
            from_desc,
            to_desc,
            k=1,
            reverse_direction=True,
            formated_string=True
        )

        if paths:
            print(f"\n   Shortest path:")
            print(f"   {paths[0]}")
        else:
            print(f"\n   No path found")

        # Calculate distance
        distance = graph.distance_between_descriptions(
            from_desc,
            to_desc,
            reverse_direction=True,
            weighted=False
        )
        print(f"\n   Distance: {distance} hops")
    else:
        print("\n   Could not find suitable descriptions for path example")

    # Example 4: Connection types
    print("\n" + "=" * 70)
    print("Example 4: Check Connection Types")
    print("=" * 70)

    if test_leaf and parents:
        parent = parents[0]
        connection = graph.get_connection(
            parent,
            test_leaf,
            formated_string=True
        )
        print(f"\n   Connection: {connection}")

        # Get raw connection type
        conn_type = graph.get_connection(
            parent,
            test_leaf,
            formated_string=False
        )
        print(f"   Type: '{conn_type}'")

    # Example 5: Subgraph
    print("\n" + "=" * 70)
    print("Example 5: Create Subgraph")
    print("=" * 70)

    # Find a description with children
    parent_desc = None
    for desc in graph.descriptions:
        children = graph.children_of_description(desc)
        if len(children) >= 2:
            parent_desc = desc
            break

    if parent_desc:
        print(f"\n   Creating subgraph from '{parent_desc}'...")
        subgraph = graph.subgraph_induced_from_description(parent_desc)

        print(f"   ✓ Subgraph created")
        print(f"   Root: {subgraph.root}")
        print(f"   Descriptions: {len(subgraph.descriptions)}")
        print(f"\n   First 5 descriptions in subgraph:")
        for desc in subgraph.descriptions[:5]:
            print(f"     - {desc}")
    else:
        print("\n   Could not find suitable description for subgraph example")

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print("\n   ✓ Successfully loaded and explored the SYSTEM graph")
    print("   ✓ All graph traversal operations working correctly")
    print("\n   For more operations, see FlavorGraphTraverser/graph.py")
    print("   or check the docstrings: help(CoffeeDescriptionGraph)")
    print("\n" + "=" * 70)

    return 0


if __name__ == '__main__':
    exit(main())
