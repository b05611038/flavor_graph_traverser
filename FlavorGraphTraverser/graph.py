"""
Coffee Description Graph Module
================================

This module provides a directed acyclic graph (DAG) representation of coffee flavor
descriptions and their hierarchical relationships.

The CoffeeDescriptionGraph class wraps igraph.Graph to provide domain-specific
methods for navigating and analyzing flavor relationships.
"""

import copy
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from igraph import Graph, plot

from .constants import description_graph_connections, DEFAULT_CONNECTION_DISTANCES
from .utils import (
    boolean_check,
    integer_check,
    string_check,
    list_check,
    dict_check,
    lprint,
)


__all__ = ["CoffeeDescriptionGraph"]


class CoffeeDescriptionGraph:
    """
    A directed acyclic graph (DAG) representing coffee flavor descriptions.

    This class provides methods for navigating hierarchical flavor relationships,
    computing distances between flavors, and analyzing the graph structure.

    Attributes:
        descriptions: List of all description names in the graph
        graph: The directed igraph.Graph object
        undirected_graph: Bidirectional version for reverse traversal
        root: Optional root node name
        graph_name: Name identifier for this graph
        connection_distances: Weights for different edge types
        dynamic: Whether the graph allows modification after initialization

    Example:
        >>> descriptions = ['root', 'floral', 'rose', 'jasmine']
        >>> connections = [
        ...     {'source': 'root', 'target': 'floral', 'path_type': 'sub-category'},
        ...     {'source': 'floral', 'target': 'rose', 'path_type': 'sub-category'},
        ...     {'source': 'floral', 'target': 'jasmine', 'path_type': 'sub-category'},
        ... ]
        >>> graph = CoffeeDescriptionGraph(descriptions, connections, root='root')
        >>> graph.children_of_description('floral')
        ['rose', 'jasmine']
        >>> graph.distance_between_descriptions('rose', 'jasmine')
        2.0
    """

    def __init__(
        self,
        descriptions: List[str],
        connections: List[Dict[str, str]],
        root: Optional[str] = None,
        graph_name: str = "SYSTEM",
        connection_distances: Optional[Dict[str, Dict[str, float]]] = None,
        connection_text_length: int = 20,
        dynamic: bool = False,
    ):
        """
        Initialize a CoffeeDescriptionGraph.

        Args:
            descriptions: List of flavor description names
            connections: List of connection dicts with 'source', 'target', 'path_type'
            root: Optional root node name
            graph_name: Identifier for this graph
            connection_distances: Optional weight dict for edge types
            connection_text_length: Text width for formatted connection strings
            dynamic: If True, allows modifications after initialization

        Raises:
            TypeError: If arguments are not of the expected types
            ValueError: If connections reference non-existent descriptions
        """
        self.dynamic = dynamic
        self.__init_done = False
        self.__descriptions: List[str] = []
        self._graph = Graph(directed=True)
        self._undirected_graph = Graph(directed=False)

        self.graph_name = graph_name
        self.connection_distances = connection_distances
        self.connection_text_length = connection_text_length

        descriptions = list_check(descriptions, "descriptions")
        for des in descriptions:
            self.add_description(des)

        connections = list_check(connections, "connections")
        for conn in connections:
            self.add_connection(conn)

        self.root = root
        self.__init_done = True

    @property
    def descriptions(self) -> List[str]:
        """Get a copy of all description names."""
        return copy.deepcopy(self.__descriptions)

    @property
    def graph(self) -> Graph:
        """Get the directed graph object."""
        return self._graph

    @property
    def undirected_graph(self) -> Graph:
        """Get the undirected (bidirectional) graph object."""
        return self._undirected_graph

    @property
    def root(self) -> Optional[str]:
        """Get the root node name."""
        return self._root

    @root.setter
    def root(self, root: Optional[str]) -> None:
        """Set the root node name."""
        if root is not None:
            root = string_check(root, "root", valid_candidates=self.descriptions)
        self._root = root

    @property
    def graph_name(self) -> str:
        """Get the graph name."""
        return self._graph_name

    @graph_name.setter
    def graph_name(self, graph_name: str) -> None:
        """Set the graph name."""
        graph_name = string_check(graph_name, "graph_name")
        self._graph_name = graph_name

    @property
    def connection_distances(self) -> Optional[Dict[str, Dict[str, float]]]:
        """Get the connection distance weights."""
        return self._connection_distances

    @connection_distances.setter
    def connection_distances(
        self, connection_distances: Optional[Dict[str, Dict[str, float]]]
    ) -> None:
        """Set the connection distance weights."""
        if connection_distances is not None:
            connection_distances = dict_check(
                connection_distances,
                "connection_distances",
                necessary_keys=["forward", "reverse"],
            )

            for direction in ["forward", "reverse"]:
                connection_distances[direction] = dict_check(
                    connection_distances[direction],
                    f"connection_distances['{direction}']",
                    necessary_keys=description_graph_connections,
                )

        self._connection_distances = connection_distances

    @property
    def connection_text_length(self) -> int:
        """Get the connection text length for formatting."""
        return self._connection_text_length

    @connection_text_length.setter
    def connection_text_length(self, connection_text_length: int) -> None:
        """Set the connection text length for formatting."""
        connection_text_length = integer_check(
            connection_text_length, "connection_text_length", (1, None)
        )
        self._connection_text_length = connection_text_length

    @property
    def dynamic(self) -> bool:
        """Check if the graph is dynamic (modifiable)."""
        return self._dynamic

    @dynamic.setter
    def dynamic(self, dynamic: bool) -> None:
        """Set whether the graph is dynamic."""
        self._dynamic = boolean_check(dynamic, "dynamic")

    def __repr__(self) -> str:
        """String representation of the graph."""
        lines = (
            f"{self.__class__.__name__}(graph_name='{self.graph_name}', "
            f"dynamic={self.dynamic})\n"
        )
        lines += "Topological structure of coffee descriptions is stored in this object.\n"
        return lines

    def help(self) -> None:
        """Print available methods and usage information."""
        lines = self.__repr__()
        lines += "\nSupported methods:\n"
        not_display_method = [
            "descriptions",
            "graph",
            "undirected_graph",
            "root",
            "graph_name",
            "connection_distances",
            "connection_text_length",
            "dynamic",
        ]

        if not self.dynamic:
            not_display_method += [
                "add_description",
                "delete_description",
                "add_connection",
                "delete_connection",
            ]

        for method in self.__class__.__dict__.keys():
            if method in not_display_method:
                continue

            if method[0] != "_":
                lines += f"{self.__class__.__name__}.{method}\n"

        lprint(lines[:-1])

    def _add_description(self, description_name: str) -> None:
        """Internal method to add a description node."""
        self.__descriptions.append(description_name)
        self.graph.add_vertices(1)
        self.graph.vs[-1]["name"] = description_name
        self.graph.vs[-1]["label"] = description_name
        self.undirected_graph.add_vertices(1)
        self.undirected_graph.vs[-1]["name"] = description_name
        self.undirected_graph.vs[-1]["label"] = description_name

    def add_description(self, description_name: str) -> None:
        """
        Add a description node to the graph.

        Args:
            description_name: Name of the flavor description to add

        Raises:
            TypeError: If description_name is not a string
        """
        description_name = string_check(description_name, "description_name")

        if self.dynamic:
            self._add_description(description_name)
        else:
            if not self.__init_done:
                self._add_description(description_name)
            else:
                lprint(
                    f"Because {self.__class__.__name__}.dynamic=False, "
                    "cannot add description into graph."
                )

    def delete_description(self, description_name: str) -> None:
        """
        Delete a description node from the graph.

        Args:
            description_name: Name of the flavor description to delete

        Raises:
            TypeError: If description_name is not a string
            ValueError: If description doesn't exist
        """
        description_name = string_check(
            description_name, "description_name", valid_candidates=self.descriptions
        )

        if self.dynamic:
            description_index = self.graph.vs["label"].index(description_name)
            self.graph.delete_vertices(description_index)
            description_index = self.undirected_graph.vs["label"].index(description_name)
            self.undirected_graph.delete_vertices(description_index)
            self.__descriptions.remove(description_name)
        else:
            lprint(
                f"Because {self.__class__.__name__}.dynamic=False, "
                "cannot delete description in graph."
            )

    def _add_connection(self, connection: Dict[str, str]) -> None:
        """Internal method to add a connection edge."""
        source = connection.get("source", None)
        target = connection.get("target", None)
        path_type = connection.get("path_type", "unknown")

        forward_weight, reverse_weight = None, None
        if self.connection_distances is not None:
            forward_weight = self.connection_distances["forward"].get(path_type)
            reverse_weight = self.connection_distances["reverse"].get(path_type)

        source_idx = self.graph.vs.find(source).index
        target_idx = self.graph.vs.find(target).index
        self.graph.add_edges([(source_idx, target_idx)])
        self.graph.es[-1]["label"] = path_type
        if forward_weight is not None:
            self.graph.es[-1]["weight"] = forward_weight

        source_idx = self.undirected_graph.vs.find(source).index
        target_idx = self.undirected_graph.vs.find(target).index
        self.undirected_graph.add_edges([(source_idx, target_idx)])
        self.undirected_graph.es[-1]["label"] = path_type
        if forward_weight is not None:
            self.undirected_graph.es[-1]["weight"] = forward_weight

        self.undirected_graph.add_edges([(target_idx, source_idx)])
        self.undirected_graph.es[-1]["label"] = f"{path_type} (R)"
        if reverse_weight is not None:
            self.undirected_graph.es[-1]["weight"] = reverse_weight

    def add_connection(self, connection: Dict[str, str]) -> None:
        """
        Add a connection edge between descriptions.

        Args:
            connection: Dict with 'source', 'target', and 'path_type' keys

        Raises:
            TypeError: If connection is not a dict
            KeyError: If required keys are missing
        """
        connection = dict_check(
            connection, "connection", necessary_keys=["source", "target", "path_type"]
        )
        if self.dynamic:
            self._add_connection(connection)
        else:
            if not self.__init_done:
                self._add_connection(connection)
            else:
                lprint(
                    f"Because {self.__class__.__name__}.dynamic=False, "
                    "cannot add connection into graph."
                )

    def _delete_connection_in_graph(
        self, graph_object: Graph, description: str, another_description: str
    ) -> None:
        """Internal method to delete connections in a graph object."""
        index = graph_object.vs["label"].index(description)
        another_index = graph_object.vs["label"].index(another_description)
        existing_connection_ids = []
        if graph_object.are_connected(index, another_index):
            connection_id = graph_object.get_eid(index, another_index)
            existing_connection_ids.append(connection_id)

        if graph_object.are_connected(another_index, index):
            connection_id = graph_object.get_eid(another_index, index)
            existing_connection_ids.append(connection_id)

        if len(existing_connection_ids) > 0:
            graph_object.delete_edges(existing_connection_ids)

    def delete_connection(self, description: str, another_description: str) -> None:
        """
        Delete all connections between two descriptions.

        Args:
            description: First description name
            another_description: Second description name

        Raises:
            TypeError: If arguments are not strings
            ValueError: If descriptions don't exist
        """
        description = string_check(
            description, "description", valid_candidates=self.descriptions
        )
        another_description = string_check(
            another_description, "another_description", valid_candidates=self.descriptions
        )

        if self.dynamic:
            self._delete_connection_in_graph(self.graph, description, another_description)
            self._delete_connection_in_graph(
                self.undirected_graph, description, another_description
            )
        else:
            lprint(
                f"Because {self.__class__.__name__}.dynamic=False, "
                "cannot delete connection in graph."
            )

    def get_connection(
        self,
        description: str,
        another_description: str,
        reverse_direction: bool = True,
        formated_string: bool = True,
    ) -> Optional[str]:
        """
        Get the connection type between two descriptions.

        Args:
            description: First description name
            another_description: Second description name
            reverse_direction: If True, check reverse connections too
            formated_string: If True, return formatted string; else return path_type only

        Returns:
            Connection string/type or None if no connection exists

        Example:
            >>> graph.get_connection('floral', 'rose')
            'floral  --[sub-category]->  rose'
            >>> graph.get_connection('floral', 'rose', formated_string=False)
            'sub-category'
        """
        description = string_check(
            description, "description", valid_candidates=self.descriptions
        )
        another_description = string_check(
            another_description, "another_description", valid_candidates=self.descriptions
        )
        reverse_direction = boolean_check(reverse_direction, "reverse_direction")
        formated_string = boolean_check(formated_string, "formated_string")

        conn_type = None
        index = self.graph.vs["label"].index(description)
        another_index = self.graph.vs["label"].index(another_description)

        if self.graph.are_connected(index, another_index):
            conn_id = self.graph.get_eid(index, another_index)
            conn_type = self.graph.es["label"][conn_id]
            if formated_string:
                conn_type = f"--[{conn_type}]->".center(self.connection_text_length)

        elif self.graph.are_connected(another_index, index):
            if reverse_direction:
                conn_id = self.graph.get_eid(another_index, index)
                conn_type = self.graph.es["label"][conn_id]
                if formated_string:
                    conn_type = f"<-[{conn_type}]--".center(self.connection_text_length)
            else:
                if formated_string:
                    conn_type = "X".center(self.connection_text_length)
        else:
            if formated_string:
                conn_type = "X".center(self.connection_text_length)

        if formated_string and conn_type is not None:
            connection = f"{description} {conn_type} {another_description}"
        else:
            connection = conn_type

        return connection

    def valid_construction(self) -> bool:
        """
        Check if the graph is a valid DAG (directed acyclic graph).

        Returns:
            True if the graph is a DAG, False otherwise
        """
        return self.graph.is_dag()

    def parents_of_description(self, description: str) -> List[str]:
        """
        Get parent descriptions (incoming neighbors).

        Args:
            description: Description name to query

        Returns:
            List of parent description names

        Example:
            >>> graph.parents_of_description('rose')
            ['floral']
        """
        description = string_check(
            description, "description", valid_candidates=self.descriptions
        )

        index = self.graph.vs["label"].index(description)
        parent_indices = self.graph.neighbors(index, mode="in")
        parents = [self.graph.vs["label"][idx] for idx in parent_indices]
        return parents

    def children_of_description(self, description: str) -> List[str]:
        """
        Get child descriptions (outgoing neighbors).

        Args:
            description: Description name to query

        Returns:
            List of child description names

        Example:
            >>> graph.children_of_description('berry')
            ['strawberry', 'blueberry', 'blackberry', 'raspberry']
        """
        description = string_check(
            description, "description", valid_candidates=self.descriptions
        )

        index = self.graph.vs["label"].index(description)
        child_indices = self.graph.neighbors(index, mode="out")
        children = [self.graph.vs["label"][idx] for idx in child_indices]
        return children

    def pathways_between_descriptions(
        self,
        description: str,
        to_description: str,
        k: Optional[int] = None,
        reverse_direction: bool = True,
        weighted: bool = True,
        formated_string: bool = True,
    ) -> List[Union[str, List[str]]]:
        """
        Find K shortest paths between two descriptions.

        Args:
            description: Start description
            to_description: Target description
            k: Number of paths to return (default: 1)
            reverse_direction: If True, allow reverse edges
            weighted: If True, use connection weights
            formated_string: If True, return formatted strings; else return node lists

        Returns:
            List of paths (strings or node lists)

        Example:
            >>> graph.pathways_between_descriptions('root', 'rose')
            ['root  --[sub-category]->  floral  --[sub-category]->  rose']
        """
        description = string_check(
            description, "description", valid_candidates=self.descriptions
        )
        to_description = string_check(
            to_description, "to_description", valid_candidates=self.descriptions
        )

        if k is None:
            k = 1
        else:
            k = integer_check(k, "k", (1, None))

        reverse_direction = boolean_check(reverse_direction, "reverse_direction")
        weighted = boolean_check(weighted, "weighted")
        formated_string = boolean_check(formated_string, "formated_string")

        if reverse_direction:
            index = self.undirected_graph.vs["label"].index(description)
            to_index = self.undirected_graph.vs["label"].index(to_description)
        else:
            index = self.graph.vs["label"].index(description)
            to_index = self.graph.vs["label"].index(to_description)

        connection_weights = None
        if weighted:
            if self.connection_distances is not None:
                connection_weights = (
                    self.undirected_graph.es["weight"]
                    if reverse_direction
                    else self.graph.es["weight"]
                )

        if reverse_direction:
            shortest_paths = self.undirected_graph.get_k_shortest_paths(
                index, to_index, k=k, weights=connection_weights, mode="out", output="vpath"
            )
        else:
            shortest_paths = self.graph.get_k_shortest_paths(
                index, to_index, k=k, weights=connection_weights, mode="out", output="vpath"
            )

        pathways = []
        for path in shortest_paths:
            if formated_string:
                text, previous_idx = "", None
                for des_idx in path:
                    if previous_idx is not None:
                        if reverse_direction:
                            conn_id = self.undirected_graph.get_eid(previous_idx, des_idx)
                            conn_type = self.undirected_graph.es["label"][conn_id]
                            if conn_type.endswith("(R)"):
                                connection_info = f"<-[{conn_type[:-4]}]--"
                            else:
                                connection_info = f"--[{conn_type}]->"
                        else:
                            conn_id = self.graph.get_eid(previous_idx, des_idx)
                            conn_type = self.graph.es["label"][conn_id]
                            connection_info = f"--[{conn_type}]->"

                        connection_info = connection_info.center(self.connection_text_length)
                        text += " " + connection_info + " "

                    if reverse_direction:
                        text += self.undirected_graph.vs["label"][des_idx]
                    else:
                        text += self.graph.vs["label"][des_idx]

                    previous_idx = des_idx

                pathways.append(text)
            else:
                if reverse_direction:
                    pathways.append([self.undirected_graph.vs["label"][idx] for idx in path])
                else:
                    pathways.append([self.graph.vs["label"][idx] for idx in path])

        return pathways

    def distance_between_descriptions(
        self, description: str, another_description: str, reverse_direction: bool = True, weighted: bool = True
    ) -> float:
        """
        Calculate shortest distance between two descriptions.

        Args:
            description: First description
            another_description: Second description
            reverse_direction: If True, allow reverse edges
            weighted: If True, use connection weights

        Returns:
            Shortest distance (inf if no path exists)

        Example:
            >>> graph.distance_between_descriptions('root', 'rose')
            2.0
        """
        description = string_check(
            description, "description", valid_candidates=self.descriptions
        )
        another_description = string_check(
            another_description, "another_description", valid_candidates=self.descriptions
        )
        reverse_direction = boolean_check(reverse_direction, "reverse_direction")
        weighted = boolean_check(weighted, "weighted")

        if reverse_direction:
            index = self.undirected_graph.vs["label"].index(description)
            another_index = self.undirected_graph.vs["label"].index(another_description)
        else:
            index = self.graph.vs["label"].index(description)
            another_index = self.graph.vs["label"].index(another_description)

        connection_weights = None
        if weighted:
            if self.connection_distances is not None:
                if reverse_direction:
                    connection_weights = self.undirected_graph.es["weight"]
                else:
                    connection_weights = self.graph.es["weight"]

        distance = float("inf")
        if reverse_direction:
            shortest_distances = self.undirected_graph.distances(
                index, another_index, weights=connection_weights, mode="out"
            )
        else:
            shortest_distances = self.graph.distances(
                index, another_index, weights=connection_weights, mode="out"
            )

        for list_obj in shortest_distances:
            for dis in list_obj:
                distance = min(distance, float(dis))

        return distance

    def adjacency_matrix(
        self, root_description: bool = False, reverse_connection: bool = False
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Get the adjacency matrix representation.

        Args:
            root_description: If True, include root node
            reverse_connection: If True, use undirected graph

        Returns:
            Tuple of (adjacency_matrix, description_names)
        """
        root_description = boolean_check(root_description, "root_description")
        reverse_connection = boolean_check(reverse_connection, "reverse_connection")

        if reverse_connection:
            adjacency_matrix = self.undirected_graph.get_adjacency()
            description_ordering = list(self.undirected_graph.vs["label"])
        else:
            adjacency_matrix = self.graph.get_adjacency()
            description_ordering = list(self.graph.vs["label"])

        adjacency_matrix = np.array(adjacency_matrix.data, dtype=np.float32)

        if not root_description and self.root is not None:
            if reverse_connection:
                root_idx = self.undirected_graph.vs["label"].index(self.root)
            else:
                root_idx = self.graph.vs["label"].index(self.root)

            selected_indices = [i for i in range(len(description_ordering)) if i != root_idx]
            description_ordering.remove(self.root)
            adjacency_matrix = adjacency_matrix[selected_indices, :][:, selected_indices]

        return adjacency_matrix, description_ordering

    def subgraph_induced_from_description(self, description: str) -> "CoffeeDescriptionGraph":
        """
        Create a subgraph containing a description and all its descendants.

        Args:
            description: Root of the subgraph

        Returns:
            New CoffeeDescriptionGraph containing the subgraph

        Example:
            >>> subgraph = graph.subgraph_induced_from_description('floral')
            >>> subgraph.descriptions
            ['floral', 'rose', 'jasmine', 'chamomile']
        """
        description = string_check(
            description, "description", valid_candidates=self.descriptions
        )

        index = self.graph.vs["label"].index(description)

        reachable_indices = self.graph.subcomponent(index, mode="out")
        induced_graph = self.graph.induced_subgraph(reachable_indices)
        induced_descriptions = list(induced_graph.vs["label"])
        induced_descriptions.remove(description)
        induced_descriptions = [description] + induced_descriptions

        induced_connections = []
        connections_in_subgraph = induced_graph.get_edgelist()
        for conn in connections_in_subgraph:
            source_idx, target_idx = conn
            source_description = induced_graph.vs["label"][source_idx]
            target_description = induced_graph.vs["label"][target_idx]
            conn_id = induced_graph.get_eid(source_idx, target_idx)
            conn_type = induced_graph.es["label"][conn_id]
            conn_doc = {
                "source": source_description,
                "target": target_description,
                "path_type": conn_type,
            }

            induced_connections.append(conn_doc)

        induced_graph_name = self.graph_name + f" (induced from {description})"

        return CoffeeDescriptionGraph(
            induced_descriptions,
            induced_connections,
            root=description,
            graph_name=induced_graph_name,
            connection_distances=self.connection_distances,
            connection_text_length=self.connection_text_length,
            dynamic=self.dynamic,
        )

    def get_parent(self, descriptor: str) -> Optional[str]:
        """
        Get the parent of a descriptor (wrapper for parents_of_description).

        Returns the first parent, or None if no parents.

        Args:
            descriptor: Descriptor name

        Returns:
            Parent descriptor name or None

        Example:
            >>> parent = graph.get_parent("chocolate")
            >>> print(parent)  # 'cocoa'
        """
        parents = self.parents_of_description(descriptor)
        return parents[0] if parents else None

    def get_children(self, descriptor: str) -> List[str]:
        """
        Get the children of a descriptor (wrapper for children_of_description).

        Args:
            descriptor: Descriptor name

        Returns:
            List of child descriptor names

        Example:
            >>> children = graph.get_children("cocoa")
            >>> print(children)  # ['chocolate', 'dark chocolate', ...]
        """
        return self.children_of_description(descriptor)

    def get_ancestors(self, descriptor: str) -> List[str]:
        """
        Get all ancestors of a descriptor (parents, grandparents, etc.).

        Args:
            descriptor: Descriptor name

        Returns:
            List of ancestor descriptor names

        Example:
            >>> ancestors = graph.get_ancestors("chocolate")
            >>> print(ancestors)  # ['cocoa', 'nutty/cocoa', 'coffee']
        """
        ancestors = []
        current = descriptor

        while True:
            parent = self.get_parent(current)
            if parent is None:
                break
            ancestors.append(parent)
            current = parent

        return ancestors

    def get_root_categories(self) -> List[str]:
        """
        Get all root categories (first-level children of the root node).

        Returns:
            List of root category names

        Example:
            >>> roots = graph.get_root_categories()
            >>> print(roots)  # ['fruity', 'floral', 'nutty/cocoa', 'spices', 'roasted']
        """
        if self.root is None:
            return []
        return self.get_children(self.root)

    def get_leaf_nodes(self) -> List[str]:
        """
        Get all leaf nodes (nodes with no children).

        Returns:
            List of leaf node names

        Example:
            >>> leaves = graph.get_leaf_nodes()
            >>> print(len(leaves))  # Number of leaf descriptors
        """
        leaf_nodes = []
        for descriptor in self.descriptions:
            children = self.get_children(descriptor)
            if not children:
                leaf_nodes.append(descriptor)
        return leaf_nodes

    def get_middle_nodes(self) -> List[str]:
        """
        Get all middle nodes (nodes with both parent and children).

        Returns:
            List of middle node names

        Example:
            >>> middle = graph.get_middle_nodes()
            >>> # Returns nodes that are neither root nor leaves
        """
        middle_nodes = []
        for descriptor in self.descriptions:
            if descriptor == self.root:
                continue
            parent = self.get_parent(descriptor)
            children = self.get_children(descriptor)
            if parent and children:
                middle_nodes.append(descriptor)
        return middle_nodes

    def get_path_distance(self, source: str, target: str) -> Optional[int]:
        """
        Get the shortest path distance between two descriptors.

        Args:
            source: Source descriptor
            target: Target descriptor

        Returns:
            Path distance (number of edges) or None if no path exists

        Example:
            >>> distance = graph.get_path_distance("chocolate", "fruity")
            >>> print(distance)  # e.g., 4 (number of hops)
        """
        if source not in self.descriptions or target not in self.descriptions:
            return None

        source_idx = self.graph.vs.find(label=source).index
        target_idx = self.graph.vs.find(label=target).index

        try:
            # Get shortest path
            path = self.undirected_graph.get_shortest_paths(
                source_idx,
                to=target_idx,
                mode="all",
                output="vpath"
            )

            if not path or not path[0]:
                return None

            # Distance is path length minus 1 (number of edges)
            return len(path[0]) - 1

        except:
            return None

    def get_root_category(self, descriptor: str) -> Optional[str]:
        """
        Get the root category that a descriptor belongs to.

        This is the first-level child of the root node in the path
        from root to descriptor.

        Args:
            descriptor: Descriptor name

        Returns:
            Root category name or None if not found

        Example:
            >>> root_cat = graph.get_root_category("chocolate")
            >>> print(root_cat)  # 'nutty/cocoa'
        """
        if descriptor not in self.descriptions:
            return None

        if self.root is None:
            return None

        # Traverse up to find root category
        ancestors = self.get_ancestors(descriptor)

        if not ancestors:
            # descriptor might be a root category itself
            if descriptor in self.get_children(self.root):
                return descriptor
            return None

        # Find the ancestor that is a child of root
        root_children = set(self.get_children(self.root))

        # Traverse ancestors from bottom to top
        for ancestor in reversed(ancestors):
            if ancestor in root_children:
                return ancestor

        return None

    def find_lca(self, descriptor1: str, descriptor2: str) -> Optional[str]:
        """
        Find the lowest common ancestor (LCA) of two descriptors.

        Args:
            descriptor1: First descriptor
            descriptor2: Second descriptor

        Returns:
            LCA descriptor or None if no common ancestor

        Example:
            >>> lca = graph.find_lca("chocolate", "caramel")
            >>> print(lca)  # Might be 'sweet' or 'nutty/cocoa' depending on structure
        """
        if descriptor1 not in self.descriptions or descriptor2 not in self.descriptions:
            return None

        # Get ancestors of both (including the nodes themselves)
        ancestors1 = set(self.get_ancestors(descriptor1) + [descriptor1])
        ancestors2 = set(self.get_ancestors(descriptor2) + [descriptor2])

        # Find common ancestors
        common_ancestors = ancestors1 & ancestors2

        if not common_ancestors:
            return None

        # Find the lowest (furthest from root)
        # For each common ancestor, count its distance from root
        lca = None
        max_depth = -1

        for ancestor in common_ancestors:
            # Count depth (number of ancestors)
            depth = len(self.get_ancestors(ancestor))
            if depth > max_depth:
                max_depth = depth
                lca = ancestor

        return lca

    def plot(self, *args: Any, **kwargs: Any) -> Any:
        """
        Plot the graph using igraph's plotting functionality.

        Args:
            *args: Positional arguments passed to igraph.plot
            **kwargs: Keyword arguments passed to igraph.plot

        Returns:
            Plot object

        Example:
            >>> graph.plot('graph.png')
        """
        return plot(self.graph, *args, **kwargs)
