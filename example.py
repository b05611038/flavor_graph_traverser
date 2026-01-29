"""
Example usage of the Flavor Graph Traverser package.

This script demonstrates the core functionality of CoffeeDescriptionGraph
for building and querying coffee flavor hierarchies.
"""

from FlavorGraphTraverser import CoffeeDescriptionGraph
from FlavorGraphTraverser.flavor_categories import INNER_CATEGORIES, CATEGORY_EXAMPLES


def main():
    print("=" * 60)
    print("Flavor Graph Traverser - Example Usage")
    print("=" * 60)

    # 1. Show flavor categories
    print("\n1. Standard Coffee Flavor Categories (Inner Layer):")
    print("-" * 60)
    for i, category in enumerate(INNER_CATEGORIES, 1):
        examples = CATEGORY_EXAMPLES.get(category, [])[:3]  # Show first 3 examples
        print(f"  {i}. {category:20s} - e.g., {', '.join(examples)}")

    # 2. Build a simple flavor graph
    print("\n2. Building a Simple Flavor Graph:")
    print("-" * 60)

    descriptions = ['root', 'floral', 'fruity', 'rose', 'jasmine', 'berry', 'citrus']
    connections = [
        {'source': 'root', 'target': 'floral', 'path_type': 'sub-category'},
        {'source': 'root', 'target': 'fruity', 'path_type': 'sub-category'},
        {'source': 'floral', 'target': 'rose', 'path_type': 'sub-category'},
        {'source': 'floral', 'target': 'jasmine', 'path_type': 'sub-category'},
        {'source': 'fruity', 'target': 'berry', 'path_type': 'sub-category'},
        {'source': 'fruity', 'target': 'citrus', 'path_type': 'sub-category'},
    ]

    graph = CoffeeDescriptionGraph(descriptions, connections, root='root')
    print(f"  Created graph with {len(descriptions)} nodes")
    print(f"  Valid DAG: {graph.valid_construction()}")

    # 3. Query graph structure
    print("\n3. Graph Queries:")
    print("-" * 60)

    print(f"  Children of 'root': {graph.children_of_description('root')}")
    print(f"  Children of 'floral': {graph.children_of_description('floral')}")
    print(f"  Parents of 'rose': {graph.parents_of_description('rose')}")

    # 4. Find paths
    print("\n4. Path Finding:")
    print("-" * 60)

    paths = graph.pathways_between_descriptions('root', 'rose', k=1)
    print(f"  Path from 'root' to 'rose':")
    print(f"    {paths[0]}")

    # 5. Calculate distances
    print("\n5. Distance Calculations:")
    print("-" * 60)

    distance1 = graph.distance_between_descriptions('rose', 'jasmine')
    print(f"  Distance between 'rose' and 'jasmine': {distance1}")

    distance2 = graph.distance_between_descriptions('rose', 'berry')
    print(f"  Distance between 'rose' and 'berry': {distance2}")

    # 6. Get connection info
    print("\n6. Connection Information:")
    print("-" * 60)

    conn = graph.get_connection('floral', 'rose')
    print(f"  Connection: {conn}")

    # 7. Subgraph extraction
    print("\n7. Subgraph Extraction:")
    print("-" * 60)

    subgraph = graph.subgraph_induced_from_description('floral')
    print(f"  Subgraph rooted at 'floral': {subgraph.descriptions}")

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
