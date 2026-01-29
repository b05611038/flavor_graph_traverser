#!/usr/bin/env python3
"""
Pack SYSTEM Graph from coffee_database
=======================================

Extract the SYSTEM graph from the running coffee_database and save it
in portable JSON/pickle formats for FlavorGraphTraverser.

This script connects to your MongoDB-backed coffee_database and extracts:
- All flavor descriptions in the SYSTEM graph
- All connections (hierarchical relationships)
- Root node and metadata

Prerequisites:
    - coffee_database module installed and accessible
    - MongoDB server running with coffee data
    - Run from the flavor_graph_traverser directory

Usage:
    python pack_system_graph.py

Output:
    - system_graph_data.json: Human-readable graph structure
    - system_graph_data.pkl: Fast-loading binary format
"""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Any


def extract_system_graph_from_database() -> Dict[str, Any]:
    """
    Extract SYSTEM graph from coffee_database.

    Returns:
        dict: Complete graph data with descriptions, connections, and metadata
    """
    print("="*70)
    print("Extracting SYSTEM Graph from coffee_database")
    print("="*70)

    # Import coffee_database
    try:
        from coffee_database import CoffeeDatabase
        from coffee_database.description.graph import description_graph_from_database
    except ImportError as e:
        raise ImportError(
            f"Cannot import coffee_database: {e}\n"
            "Please ensure:\n"
            "1. coffee_database is installed\n"
            "2. MongoDB server is running\n"
            "3. Database is properly configured"
        )

    # Initialize database connection
    print("\n1. Connecting to coffee_database...")
    try:
        db = CoffeeDatabase()
        print("   ✓ Connected successfully")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to database: {e}")

    # List available structures
    print("\n2. Checking available graph structures...")
    try:
        structures = db.list_description_structures()
        print(f"   Available DAGs: {structures.get('DAG', [])}")
        print(f"   Available Hierarchies: {structures.get('hierarchy', [])}")

        if 'SYSTEM' not in structures.get('DAG', []):
            raise ValueError("SYSTEM graph not found in database!")
    except Exception as e:
        raise RuntimeError(f"Failed to list structures: {e}")

    # Extract SYSTEM graph using the official method
    print("\n3. Extracting SYSTEM graph...")
    try:
        graph = description_graph_from_database(
            database=db,
            graph_name='SYSTEM',
            dynamic=False
        )
        print(f"   ✓ Graph extracted: {graph.graph_name}")
        print(f"   ✓ Total descriptions: {len(graph.descriptions)}")
        print(f"   ✓ Root node: {graph.root}")
    except Exception as e:
        raise RuntimeError(f"Failed to extract graph: {e}")

    # Get connections from database
    print("\n4. Extracting connections...")
    try:
        connections_dict = db.list_all_connections_in_graph(
            graph_name='SYSTEM',
            formated_string=False
        )

        # Flatten connection dictionary into list
        # connections_dict format: {description: [list of outgoing connections]}
        flattened_connections = []
        if isinstance(connections_dict, dict):
            for description_name, conn_list in connections_dict.items():
                if isinstance(conn_list, list):
                    flattened_connections.extend(conn_list)
                elif isinstance(conn_list, dict):
                    flattened_connections.append(conn_list)
        elif isinstance(connections_dict, list):
            # Fallback: if it's already a list
            flattened_connections = connections_dict

        print(f"   ✓ Total connections: {len(flattened_connections)}")
    except Exception as e:
        raise RuntimeError(f"Failed to extract connections: {e}")

    # Verify graph structure
    print("\n5. Validating graph structure...")
    is_valid = graph.valid_construction()
    print(f"   Is valid DAG: {is_valid}")

    if not is_valid:
        raise ValueError("Extracted graph is not a valid DAG!")

    # Show sample descriptions
    print("\n6. Sample descriptions from SYSTEM graph:")
    sample_descs = graph.descriptions[:10]
    for i, desc in enumerate(sample_descs, 1):
        print(f"   {i:2d}. {desc}")
    if len(graph.descriptions) > 10:
        print(f"   ... and {len(graph.descriptions) - 10} more")

    # Show sample connections
    print("\n7. Sample connections:")
    for i, conn in enumerate(flattened_connections[:5], 1):
        source = conn.get('source', 'N/A')
        target = conn.get('target', 'N/A')
        path_type = conn.get('path_type', 'N/A')
        print(f"   {i}. {source} --[{path_type}]-> {target}")
    if len(flattened_connections) > 5:
        print(f"   ... and {len(flattened_connections) - 5} more")

    # Package data
    graph_data = {
        'graph_name': 'SYSTEM',
        'root': graph.root,
        'descriptions': graph.descriptions,
        'connections': flattened_connections,
        'metadata': {
            'num_descriptions': len(graph.descriptions),
            'num_connections': len(flattened_connections),
            'has_root': graph.root is not None,
            'is_valid_dag': is_valid,
            'extraction_source': 'coffee_database.description.graph.description_graph_from_database'
        }
    }

    return graph_data


def save_graph_data(graph_data: Dict[str, Any], output_dir: str = '.') -> None:
    """
    Save graph data to JSON and pickle formats.

    Args:
        graph_data: Dictionary containing graph structure
        output_dir: Output directory (default: current directory)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    graph_name = graph_data['graph_name'].lower()

    print("\n" + "="*70)
    print("Saving Graph Data")
    print("="*70)

    # Save as JSON
    json_file = output_path / f"{graph_name}_graph_data.json"
    print(f"\n1. Saving JSON: {json_file}")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)

    file_size = json_file.stat().st_size / 1024
    print(f"   ✓ Saved ({file_size:.2f} KB)")

    # Save as pickle
    pkl_file = output_path / f"{graph_name}_graph_data.pkl"
    print(f"\n2. Saving pickle: {pkl_file}")
    with open(pkl_file, 'wb') as f:
        pickle.dump(graph_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size = pkl_file.stat().st_size / 1024
    print(f"   ✓ Saved ({file_size:.2f} KB)")


def verify_extraction(json_file: str = 'system_graph_data.json') -> None:
    """
    Verify the extracted graph by loading and checking it.

    Args:
        json_file: Path to JSON file to verify
    """
    print("\n" + "="*70)
    print("Verification")
    print("="*70)

    print(f"\n1. Loading from {json_file}...")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("   ✓ JSON loaded successfully")
    print(f"\n2. Data structure:")
    print(f"   Graph name: {data['graph_name']}")
    print(f"   Root: {data['root']}")
    print(f"   Descriptions: {data['metadata']['num_descriptions']}")
    print(f"   Connections: {data['metadata']['num_connections']}")
    print(f"   Valid DAG: {data['metadata']['is_valid_dag']}")

    # Try loading with FlavorGraphTraverser
    print(f"\n3. Testing with FlavorGraphTraverser...")
    try:
        from FlavorGraphTraverser import CoffeeDescriptionGraph

        graph = CoffeeDescriptionGraph(
            descriptions=data['descriptions'],
            connections=data['connections'],
            root=data['root'],
            graph_name=data['graph_name']
        )

        print("   ✓ Graph object created successfully")
        print(f"   ✓ Descriptions accessible: {len(graph.descriptions)}")
        print(f"   ✓ DAG validation: {graph.valid_construction()}")

        # Test basic operations
        if graph.root:
            children = graph.children_of_description(graph.root)
            print(f"   ✓ Root has {len(children)} children")

    except Exception as e:
        print(f"   ✗ Error creating graph: {e}")
        raise


def main():
    """Main extraction workflow."""
    try:
        # Extract graph
        graph_data = extract_system_graph_from_database()

        # Save to files
        save_graph_data(graph_data, output_dir='.')

        # Verify
        verify_extraction('system_graph_data.json')

        # Success message
        print("\n" + "="*70)
        print("✓ SYSTEM Graph Successfully Packed!")
        print("="*70)

        print("\nGenerated files:")
        print("  • system_graph_data.json - Human-readable format")
        print("  • system_graph_data.pkl  - Fast binary format")

        print("\nUsage:")
        print("  from FlavorGraphTraverser import load_system_graph")
        print("  graph = load_system_graph()")
        print("  # Now use graph for question generation!")

        print("\nNext steps:")
        print("  1. Run: python example_load_graph.py")
        print("  2. Generate questions using QUESTIONS.md templates")
        print("  3. Use graph for benchmarking experiments")

        print("\n" + "="*70)
        return 0

    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Install coffee_database: pip install coffee_database")
        print("  2. Ensure MongoDB server is running")
        print("  3. Check database configuration")
        return 1

    except Exception as e:
        print(f"\n❌ Extraction Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
