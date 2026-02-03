"""
Tests for GraphToolExecutor

Tests the tool execution logic against the graph.
"""

import pytest
from FlavorGraphTraverser.evaluation.tools import (
    GraphToolExecutor,
    TOOL_VALIDATE,
    TOOL_GET_PARENT,
    TOOL_GET_CHILDREN
)


class TestGraphToolExecutor:
    """Test GraphToolExecutor functionality."""

    def test_executor_initialization(self, coffee_flavor_wheel_graph):
        """Should initialize with a graph."""
        executor = GraphToolExecutor(coffee_flavor_wheel_graph)
        assert executor.graph == coffee_flavor_wheel_graph

    def test_validate_descriptors_all_valid(self, graph_executor, sample_descriptors):
        """Should correctly identify all valid descriptors."""
        valid_descs = sample_descriptors['valid']
        result = graph_executor.validate_descriptors(valid_descs)

        assert 'valid' in result
        assert 'invalid' in result
        assert set(result['valid']) == set(valid_descs)
        assert len(result['invalid']) == 0

    def test_validate_descriptors_all_invalid(self, graph_executor, sample_descriptors):
        """Should correctly identify all invalid descriptors."""
        invalid_descs = sample_descriptors['invalid']
        result = graph_executor.validate_descriptors(invalid_descs)

        assert 'valid' in result
        assert 'invalid' in result
        assert len(result['valid']) == 0
        assert set(result['invalid']) == set(invalid_descs)

    def test_validate_descriptors_mixed(self, graph_executor, sample_descriptors):
        """Should correctly separate valid and invalid descriptors."""
        valid_descs = sample_descriptors['valid'][:2]
        invalid_descs = sample_descriptors['invalid'][:2]
        mixed_descs = valid_descs + invalid_descs

        result = graph_executor.validate_descriptors(mixed_descs)

        assert set(result['valid']) == set(valid_descs)
        assert set(result['invalid']) == set(invalid_descs)

    def test_validate_descriptors_max_limit(self, graph_executor):
        """Should limit to 10 descriptors."""
        many_descs = [f"desc_{i}" for i in range(20)]
        result = graph_executor.validate_descriptors(many_descs)

        # Should only process first 10
        total_checked = len(result['valid']) + len(result['invalid'])
        assert total_checked == 10

    def test_get_parent_valid_descriptor(self, graph_executor, coffee_flavor_wheel_graph):
        """Should return parent for valid descriptor."""
        # Find a descriptor that has a parent
        all_descs = coffee_flavor_wheel_graph.descriptions
        descriptor = None

        for desc in all_descs:
            parents = coffee_flavor_wheel_graph.parents_of_description(desc)
            if len(parents) > 0:
                descriptor = desc
                expected_parents = parents
                break

        if descriptor is None:
            pytest.skip("No descriptor with parents found in graph")

        result = graph_executor.get_parent(descriptor)

        assert result['descriptor'] == descriptor
        assert result['error'] is None
        assert result['parents'] == expected_parents

    def test_get_parent_invalid_descriptor(self, graph_executor):
        """Should return error for invalid descriptor."""
        result = graph_executor.get_parent('nonexistent_descriptor')

        assert result['descriptor'] == 'nonexistent_descriptor'
        assert result['parents'] is None
        assert result['error'] is not None
        assert 'not found' in result['error']

    def test_get_parent_root_node(self, graph_executor, coffee_flavor_wheel_graph):
        """Should return empty list for root node."""
        root = coffee_flavor_wheel_graph.root
        if root is None:
            pytest.skip("Graph has no root")

        result = graph_executor.get_parent(root)

        assert result['descriptor'] == root
        assert result['error'] is None
        assert result['parents'] == []

    def test_get_children_valid_descriptor(self, graph_executor, coffee_flavor_wheel_graph):
        """Should return children for valid descriptor."""
        # Find a descriptor that has children
        all_descs = coffee_flavor_wheel_graph.descriptions
        descriptor = None

        for desc in all_descs:
            children = coffee_flavor_wheel_graph.children_of_description(desc)
            if len(children) > 0:
                descriptor = desc
                expected_children = children
                break

        if descriptor is None:
            pytest.skip("No descriptor with children found in graph")

        result = graph_executor.get_children(descriptor)

        assert result['descriptor'] == descriptor
        assert result['error'] is None
        assert result['children'] == expected_children

    def test_get_children_invalid_descriptor(self, graph_executor):
        """Should return error for invalid descriptor."""
        result = graph_executor.get_children('nonexistent_descriptor')

        assert result['descriptor'] == 'nonexistent_descriptor'
        assert result['children'] is None
        assert result['error'] is not None
        assert 'not found' in result['error']

    def test_get_children_leaf_node(self, graph_executor, coffee_flavor_wheel_graph):
        """Should return empty list for leaf node."""
        # Find a leaf node (no children)
        all_descs = coffee_flavor_wheel_graph.descriptions
        leaf_descriptor = None

        for desc in all_descs:
            children = coffee_flavor_wheel_graph.children_of_description(desc)
            if len(children) == 0:
                leaf_descriptor = desc
                break

        if leaf_descriptor is None:
            pytest.skip("No leaf node found in graph")

        result = graph_executor.get_children(leaf_descriptor)

        assert result['descriptor'] == leaf_descriptor
        assert result['error'] is None
        assert result['children'] == []

    def test_execute_validate(self, graph_executor, sample_descriptors):
        """Should execute validate_descriptors via execute()."""
        valid_descs = sample_descriptors['valid']
        result = graph_executor.execute(TOOL_VALIDATE, {'descriptors': valid_descs})

        assert 'valid' in result
        assert 'invalid' in result

    def test_execute_get_parent(self, graph_executor, sample_descriptors):
        """Should execute get_parent via execute()."""
        descriptor = sample_descriptors['valid'][0]
        result = graph_executor.execute(TOOL_GET_PARENT, {'descriptor': descriptor})

        assert 'descriptor' in result
        assert 'parents' in result

    def test_execute_get_children(self, graph_executor, sample_descriptors):
        """Should execute get_children via execute()."""
        descriptor = sample_descriptors['valid'][0]
        result = graph_executor.execute(TOOL_GET_CHILDREN, {'descriptor': descriptor})

        assert 'descriptor' in result
        assert 'children' in result

    def test_execute_unknown_tool(self, graph_executor):
        """Should raise ValueError for unknown tool."""
        with pytest.raises(ValueError, match="Unknown tool"):
            graph_executor.execute('unknown_tool', {})

    def test_is_valid_descriptor(self, graph_executor, sample_descriptors):
        """Should check descriptor validity."""
        valid_desc = sample_descriptors['valid'][0]
        invalid_desc = sample_descriptors['invalid'][0]

        assert graph_executor.is_valid_descriptor(valid_desc) is True
        assert graph_executor.is_valid_descriptor(invalid_desc) is False
