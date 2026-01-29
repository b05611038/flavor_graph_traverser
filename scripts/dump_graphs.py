#!/usr/bin/env python3
"""
Simple script to dump graphs from coffee_database to pickle files.
"""

import pickle
from coffee_database import CoffeeDatabase
from coffee_database.description.graph import description_graph_from_database


def dump_graph(db, graph_name, output_file):
    """Extract and save a graph from database."""
    print(f"Extracting {graph_name}...")

    # Extract graph using official API
    graph = description_graph_from_database(db, graph_name=graph_name, dynamic=False)

    # Prepare data
    connections_dict = db.list_all_connections_in_graph(
        graph_name=graph_name,
        formated_string=False
    )

    # Flatten connections
    connections = []
    if isinstance(connections_dict, dict):
        for desc, conn_list in connections_dict.items():
            if isinstance(conn_list, list):
                connections.extend(conn_list)

    # Package data
    graph_data = {
        'graph_name': graph_name,
        'root': graph.root,
        'descriptions': graph.descriptions,
        'connections': connections,
    }

    # Save as pickle
    with open(output_file, 'wb') as f:
        pickle.dump(graph_data, f)

    print(f"  ✓ Saved to {output_file}")
    print(f"  ✓ {len(graph.descriptions)} descriptions, {len(connections)} connections")
    return graph_data


if __name__ == '__main__':
    # Connect to database
    print("Connecting to coffee_database...")
    db = CoffeeDatabase()

    # Dump SYSTEM graph
    dump_graph(db, 'SYSTEM', 'system_graph.pkl')

    # Dump coffee_flavor_wheel graph
    dump_graph(db, 'coffee_flavor_wheel', 'coffee_flavor_wheel.pkl')

    print("\n✓ Done! You can now load graphs from .pkl files")
    print("\nUsage:")
    print("  from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph")
    print("  data = load_graph_data('system_graph.pkl')")
    print("  graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])")
