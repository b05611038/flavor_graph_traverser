"""
Graph Tool Executor

Executes tool calls against the CoffeeDescriptionGraph.
Wraps existing graph methods and provides the tool interface.
"""

from typing import List, Dict, Any, Optional
from ...graph import CoffeeDescriptionGraph
from .definitions import TOOL_VALIDATE, TOOL_GET_PARENT, TOOL_GET_CHILDREN
from .label_resolver import LabelResolver

NOT_FOUND_MSG = (
    "Descriptor '{descriptor}' not found in graph. The graph stores short descriptors — "
    "if this is a multi-word phrase, try each component word separately with validate_descriptors."
)


class GraphToolExecutor:
    """
    Executor for graph tool calls.

    Wraps CoffeeDescriptionGraph methods to provide tool interface for LLMs.

    Example:
        >>> from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
        >>> data = load_graph_data('data/graphs/coffee_flavor_wheel.json')
        >>> graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])
        >>> executor = GraphToolExecutor(graph)
        >>>
        >>> # Validate descriptors
        >>> result = executor.execute('validate_descriptors', {'descriptors': ['rose', 'chocolate', 'unknown']})
        >>> print(result)
        >>> {'valid': ['rose', 'chocolate'], 'invalid': ['unknown']}
        >>>
        >>> # Get parent
        >>> result = executor.execute('get_parent', {'descriptor': 'blueberry'})
        >>> print(result)
        >>> {'descriptor': 'blueberry', 'parents': ['berry'], 'error': None}
    """

    def __init__(self, graph: CoffeeDescriptionGraph, resolver: Optional[LabelResolver] = None):
        """
        Initialize the executor.

        Args:
            graph: CoffeeDescriptionGraph instance to query
            resolver: Optional LabelResolver. None (default) = exact string match,
                the behaviour of the original experiment. With a resolver, bare
                layered labels ("floral"), benchmark spellings ("green/vegetable")
                and case/underscore variants resolve to canonical node names, and
                each response reports the canonical name it resolved to.
        """
        self.graph = graph
        self.resolver = resolver

    def _display(self, node: str) -> str:
        """Name shown to the model (resolver corrects tool-graph misspellings)."""
        return self.resolver.display(node) if self.resolver is not None else node

    def _resolve(self, descriptor: Any) -> Optional[str]:
        """Canonical node name for descriptor, or None if absent."""
        if self.resolver is not None:
            return self.resolver.resolve(descriptor)
        if isinstance(descriptor, str) and descriptor in self.graph.descriptions:
            return descriptor
        return None

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments dict

        Returns:
            Tool result dict

        Raises:
            ValueError: If tool_name is not recognized
        """
        if tool_name == TOOL_VALIDATE:
            return self.validate_descriptors(**arguments)
        elif tool_name == TOOL_GET_PARENT:
            return self.get_parent(**arguments)
        elif tool_name == TOOL_GET_CHILDREN:
            return self.get_children(**arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def validate_descriptors(self, descriptors: List[str]) -> Dict[str, Any]:
        """
        Validate whether descriptors exist in the graph.

        Args:
            descriptors: List of descriptor names to validate (max 10)

        Returns:
            Dict with 'valid' and 'invalid' lists

        Example:
            >>> executor.validate_descriptors(['rose', 'unknown'])
            {'valid': ['rose'], 'invalid': ['unknown']}
        """
        # Limit to 10 descriptors
        truncated = False
        if len(descriptors) > 10:
            descriptors = descriptors[:10]
            truncated = True

        valid = []
        invalid = []
        resolved = {}

        for descriptor in descriptors:
            canonical = self._resolve(descriptor) if descriptor else None
            if canonical is not None:
                valid.append(descriptor)
                shown = self._display(canonical)
                if shown != descriptor:
                    resolved[descriptor] = shown
            else:
                invalid.append(descriptor)

        result = {
            "valid": valid,
            "invalid": invalid
        }
        if resolved:
            # Only possible with a resolver: tell the model the node name to use.
            result["resolved"] = resolved
        if truncated:
            result["warning"] = "Input truncated to first 10 descriptors"
        return result

    def get_parent(self, descriptor: str) -> Dict[str, Any]:
        """
        Get parent node(s) of a descriptor.

        Args:
            descriptor: Descriptor name to query

        Returns:
            Dict with 'descriptor' and 'parents' (list)

        Raises:
            ValueError: If descriptor doesn't exist in graph

        Example:
            >>> executor.get_parent('blueberry')
            {'descriptor': 'blueberry', 'parents': ['berry'], 'error': None}
            >>> executor.get_parent('unknown')
            {'descriptor': 'unknown', 'parents': None, 'error': 'Descriptor not found in graph'}
        """
        canonical = self._resolve(descriptor)
        if canonical is None:
            return {
                "descriptor": descriptor,
                "parents": None,
                "error": NOT_FOUND_MSG.format(descriptor=descriptor)
            }

        try:
            parents = self.graph.parents_of_description(canonical)
            result = {
                "descriptor": descriptor,
                "parents": [self._display(n) for n in parents] if self.resolver is not None else parents,
                "error": None
            }
            shown = self._display(canonical)
            if shown != descriptor:
                result["resolved_to"] = shown
            return result
        except Exception as e:
            return {
                "descriptor": descriptor,
                "parents": None,
                "error": str(e)
            }

    def get_children(self, descriptor: str) -> Dict[str, Any]:
        """
        Get child node(s) of a descriptor.

        Args:
            descriptor: Descriptor name to query

        Returns:
            Dict with 'descriptor' and 'children' (list)

        Raises:
            ValueError: If descriptor doesn't exist in graph

        Example:
            >>> executor.get_children('berry')
            {'descriptor': 'berry', 'children': ['strawberry', 'blueberry', 'blackberry', 'raspberry'], 'error': None}
            >>> executor.get_children('unknown')
            {'descriptor': 'unknown', 'children': None, 'error': 'Descriptor not found in graph'}
        """
        canonical = self._resolve(descriptor)
        if canonical is None:
            return {
                "descriptor": descriptor,
                "children": None,
                "error": NOT_FOUND_MSG.format(descriptor=descriptor)
            }

        try:
            children = self.graph.children_of_description(canonical)
            result = {
                "descriptor": descriptor,
                "children": [self._display(n) for n in children] if self.resolver is not None else children,
                "error": None
            }
            shown = self._display(canonical)
            if shown != descriptor:
                result["resolved_to"] = shown
            return result
        except Exception as e:
            return {
                "descriptor": descriptor,
                "children": None,
                "error": str(e)
            }

    def is_valid_descriptor(self, descriptor: str) -> bool:
        """
        Check if a single descriptor is valid.

        Args:
            descriptor: Descriptor name

        Returns:
            True if descriptor exists in graph
        """
        return self._resolve(descriptor) is not None
