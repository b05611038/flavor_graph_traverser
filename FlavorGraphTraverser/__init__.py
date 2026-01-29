"""
FlavorGraphTraverser
====================

A library for representing and traversing coffee flavor hierarchies as directed acyclic graphs.

Main Components:
----------------
- CoffeeDescriptionGraph: DAG representation of flavor relationships
- load_system_graph: Load pre-packed SYSTEM graph without database
- load_graph_data: Load graph data from JSON/pickle files
- create_graph_from_data: Create graph from raw data structures

Basic Usage:
------------
>>> from FlavorGraphTraverser import CoffeeDescriptionGraph
>>> descriptions = ['root', 'floral', 'rose', 'jasmine']
>>> connections = [
...     {'source': 'root', 'target': 'floral', 'path_type': 'sub-category'},
...     {'source': 'floral', 'target': 'rose', 'path_type': 'sub-category'},
...     {'source': 'floral', 'target': 'jasmine', 'path_type': 'sub-category'},
... ]
>>> graph = CoffeeDescriptionGraph(descriptions, connections, root='root')
>>> graph.children_of_description('floral')
['rose', 'jasmine']

Loading Pre-packed Graph:
--------------------------
>>> from FlavorGraphTraverser import load_system_graph
>>> graph = load_system_graph()  # Loads from system_graph_data.pkl or .json
>>> graph.descriptions[:5]
"""

from .graph import CoffeeDescriptionGraph
from .loader import load_graph_data, load_system_graph, create_graph_from_data

__version__ = "0.1.0"
__all__ = [
    "CoffeeDescriptionGraph",
    "load_system_graph",
    "load_graph_data",
    "create_graph_from_data",
]
