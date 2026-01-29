#!/usr/bin/env python3
"""
Extract SYSTEM Graph from coffee_database
==========================================

This script extracts the SYSTEM graph from coffee_database and saves it
in a portable format (JSON and pickle) for use without the database.

Usage:
    python extract_system_graph.py

Output:
    - system_graph_data.json: Human-readable graph data
    - system_graph_data.pkl: Binary pickle format for fast loading
"""

import json
import pickle
from pathlib import Path


def extract_graph_from_database(database, graph_name='SYSTEM'):
    """
    Extract graph structure from coffee_database.

    Based on description_graph_from_database() from reference_code/graph.py

    Args:
        database: CoffeeDatabase instance
        graph_name: Name of the graph to extract (default: 'SYSTEM')

    Returns:
        dict: Graph data containing descriptions, connections, root, and metadata
    """
    print(f"Extracting graph: {graph_name}")

    # Get root description
    root_doc = database.invisible_root_of_the_description_structure(
        structure_name=graph_name,
        structure='DAG'
    )

    descriptions = []
    root_name = None
    if root_doc is not None:
        root_name = root_doc.get('name', None)
        if root_name:
            descriptions.append(root_name)
            print(f"  Root: {root_name}")

    # Get all descriptions in graph
    stored_descriptions = database.list_all_descriptions_in_graph(graph_name=graph_name)
    if root_name is not None and root_name in stored_descriptions:
        stored_descriptions.remove(root_name)

    descriptions += stored_descriptions
    print(f"  Total descriptions: {len(descriptions)}")

    # Get all connections
    connections = database.list_all_connections_in_graph(
        graph_name=graph_name,
        formated_string=False
    )

    # Flatten connections (from reference_code/utils.py)
    flattened_connections = []
    for conn_group in connections:
        if isinstance(conn_group, list):
            flattened_connections.extend(conn_group)
        else:
            flattened_connections.append(conn_group)

    print(f"  Total connections: {len(flattened_connections)}")

    # Package the data
    graph_data = {
        'graph_name': graph_name,
        'root': root_name,
        'descriptions': descriptions,
        'connections': flattened_connections,
        'metadata': {
            'num_descriptions': len(descriptions),
            'num_connections': len(flattened_connections),
            'has_root': root_name is not None
        }
    }

    return graph_data


def save_graph_data(graph_data, output_dir='.'):
    """
    Save graph data to JSON and pickle formats.

    Args:
        graph_data: Dictionary containing graph structure
        output_dir: Directory to save files (default: current directory)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    graph_name = graph_data['graph_name']

    # Save as JSON (human-readable)
    json_file = output_path / f"{graph_name.lower()}_graph_data.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved JSON: {json_file}")
    print(f"  Size: {json_file.stat().st_size / 1024:.2f} KB")

    # Save as pickle (fast loading)
    pkl_file = output_path / f"{graph_name.lower()}_graph_data.pkl"
    with open(pkl_file, 'wb') as f:
        pickle.dump(graph_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Saved pickle: {pkl_file}")
    print(f"  Size: {pkl_file.stat().st_size / 1024:.2f} KB")


def load_graph_data(file_path):
    """
    Load graph data from JSON or pickle file.

    Args:
        file_path: Path to .json or .pkl file

    Returns:
        dict: Graph data
    """
    file_path = Path(file_path)

    if file_path.suffix == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif file_path.suffix == '.pkl':
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")


def main():
    """Main extraction workflow."""
    try:
        # Import coffee_database
        print("Importing coffee_database...")
        from coffee_database import CoffeeDatabase

        # Initialize database
        print("Initializing CoffeeDatabase...")
        db = CoffeeDatabase()

        # List available graphs
        print("\nAvailable structures:")
        structures = db.list_description_structures()
        print(f"  DAGs: {structures.get('DAG', [])}")
        print(f"  Hierarchies: {structures.get('hierarchy', [])}")

        # Extract SYSTEM graph
        print("\n" + "="*60)
        graph_data = extract_graph_from_database(db, graph_name='SYSTEM')

        # Save to files
        print("="*60)
        save_graph_data(graph_data, output_dir='.')

        # Verify by loading
        print("\n" + "="*60)
        print("Verification: Loading from JSON...")
        loaded_data = load_graph_data('system_graph_data.json')
        print(f"  Successfully loaded {loaded_data['metadata']['num_descriptions']} descriptions")
        print(f"  Successfully loaded {loaded_data['metadata']['num_connections']} connections")

        print("\n" + "="*60)
        print("✓ Extraction complete!")
        print("\nUsage example:")
        print("  from FlavorGraphTraverser import CoffeeDescriptionGraph")
        print("  import json")
        print("  ")
        print("  # Load graph data")
        print("  with open('system_graph_data.json', 'r') as f:")
        print("      data = json.load(f)")
        print("  ")
        print("  # Create graph object")
        print("  graph = CoffeeDescriptionGraph(")
        print("      descriptions=data['descriptions'],")
        print("      connections=data['connections'],")
        print("      root=data['root'],")
        print("      graph_name=data['graph_name']")
        print("  )")

    except ImportError as e:
        print(f"\n❌ Error: Could not import coffee_database")
        print(f"   {e}")
        print("\nPlease ensure coffee_database is installed:")
        print("  pip install coffee_database")
        print("\nOr provide the path to coffee_database module")
        return 1

    except Exception as e:
        print(f"\n❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
