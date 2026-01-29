"""
Graph Data Loader
=================

Utilities for loading pre-packed graph data without requiring coffee_database.
"""

import json
import pickle
from pathlib import Path
from typing import Dict, Optional, Union

from .graph import CoffeeDescriptionGraph


def load_graph_data(file_path: Union[str, Path]) -> Dict:
    """
    Load graph data from JSON or pickle file.

    Args:
        file_path: Path to .json or .pkl file

    Returns:
        dict: Graph data containing descriptions, connections, root, and metadata

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is not supported

    Example:
        >>> data = load_graph_data('system_graph_data.json')
        >>> print(f"Loaded {data['metadata']['num_descriptions']} descriptions")
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Graph data file not found: {file_path}")

    if file_path.suffix == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif file_path.suffix == '.pkl':
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    else:
        raise ValueError(
            f"Unsupported file format: {file_path.suffix}. "
            f"Expected .json or .pkl"
        )


def load_system_graph(
    data_file: Optional[Union[str, Path]] = None,
    connection_distances: Optional[Dict] = None,
    dynamic: bool = False
) -> CoffeeDescriptionGraph:
    """
    Load the SYSTEM graph from a pre-packed data file.

    Args:
        data_file: Path to graph data file. If None, looks for default files
                  in current directory (system_graph_data.pkl or system_graph_data.json)
        connection_distances: Optional connection weights dict with 'forward' and 'reverse' keys
        dynamic: Whether to allow graph modifications after initialization

    Returns:
        CoffeeDescriptionGraph: Loaded graph object

    Raises:
        FileNotFoundError: If no graph data file is found

    Example:
        >>> from FlavorGraphTraverser import load_system_graph
        >>> graph = load_system_graph()
        >>> print(graph.descriptions[:5])
        >>> children = graph.children_of_description('floral')
    """
    # If no file specified, look for default files
    if data_file is None:
        cwd = Path.cwd()

        # Try pickle first (faster)
        pkl_file = cwd / 'system_graph_data.pkl'
        if pkl_file.exists():
            data_file = pkl_file
        else:
            # Try JSON
            json_file = cwd / 'system_graph_data.json'
            if json_file.exists():
                data_file = json_file
            else:
                raise FileNotFoundError(
                    "No SYSTEM graph data file found. "
                    "Expected 'system_graph_data.pkl' or 'system_graph_data.json' "
                    "in current directory. Run 'python extract_system_graph.py' first."
                )

    # Load data
    data = load_graph_data(data_file)

    # Create graph object
    graph = CoffeeDescriptionGraph(
        descriptions=data['descriptions'],
        connections=data['connections'],
        root=data.get('root'),
        graph_name=data.get('graph_name', 'SYSTEM'),
        connection_distances=connection_distances,
        dynamic=dynamic
    )

    return graph


def create_graph_from_data(
    descriptions: list,
    connections: list,
    root: Optional[str] = None,
    graph_name: str = "Custom",
    connection_distances: Optional[Dict] = None,
    dynamic: bool = False
) -> CoffeeDescriptionGraph:
    """
    Create a CoffeeDescriptionGraph from raw data.

    Convenience function that wraps CoffeeDescriptionGraph initialization.

    Args:
        descriptions: List of description names
        connections: List of connection dicts with 'source', 'target', 'path_type'
        root: Optional root node name
        graph_name: Name identifier for the graph
        connection_distances: Optional weights for edge types
        dynamic: Whether to allow graph modifications

    Returns:
        CoffeeDescriptionGraph: Initialized graph object

    Example:
        >>> descriptions = ['root', 'floral', 'rose']
        >>> connections = [
        ...     {'source': 'root', 'target': 'floral', 'path_type': 'sub-category'},
        ...     {'source': 'floral', 'target': 'rose', 'path_type': 'sub-category'}
        ... ]
        >>> graph = create_graph_from_data(descriptions, connections, root='root')
    """
    return CoffeeDescriptionGraph(
        descriptions=descriptions,
        connections=connections,
        root=root,
        graph_name=graph_name,
        connection_distances=connection_distances,
        dynamic=dynamic
    )


__all__ = ['load_graph_data', 'load_system_graph', 'create_graph_from_data']
