"""
Tests for Tool Definitions

Tests the function calling schemas and tool metadata.
"""

import pytest
from FlavorGraphTraverser.evaluation.tools import (
    get_tool_definitions,
    TOOL_VALIDATE,
    TOOL_GET_PARENT,
    TOOL_GET_CHILDREN
)


class TestToolDefinitions:
    """Test tool definition schemas."""

    def test_get_tool_definitions_returns_list(self):
        """Should return a list of tool definitions."""
        tools = get_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) == 3

    def test_all_tools_have_required_fields(self):
        """Each tool should have type and function fields."""
        tools = get_tool_definitions()

        for tool in tools:
            assert 'type' in tool
            assert tool['type'] == 'function'
            assert 'function' in tool

            func = tool['function']
            assert 'name' in func
            assert 'description' in func
            assert 'parameters' in func

    def test_tool_names_are_correct(self):
        """Tool names should match constants."""
        tools = get_tool_definitions()
        tool_names = [t['function']['name'] for t in tools]

        assert TOOL_VALIDATE in tool_names
        assert TOOL_GET_PARENT in tool_names
        assert TOOL_GET_CHILDREN in tool_names

    def test_validate_descriptors_schema(self):
        """validate_descriptors should have correct schema."""
        tools = get_tool_definitions()
        validate_tool = [t for t in tools if t['function']['name'] == TOOL_VALIDATE][0]

        func = validate_tool['function']
        params = func['parameters']

        # Check parameters
        assert 'descriptors' in params['properties']
        desc_param = params['properties']['descriptors']

        assert desc_param['type'] == 'array'
        assert desc_param['items']['type'] == 'string'
        assert desc_param['maxItems'] == 10
        assert desc_param['minItems'] == 1

        # Check required fields
        assert 'descriptors' in params['required']

    def test_get_parent_schema(self):
        """get_parent should have correct schema."""
        tools = get_tool_definitions()
        parent_tool = [t for t in tools if t['function']['name'] == TOOL_GET_PARENT][0]

        func = parent_tool['function']
        params = func['parameters']

        # Check parameters
        assert 'descriptor' in params['properties']
        desc_param = params['properties']['descriptor']

        assert desc_param['type'] == 'string'

        # Check required fields
        assert 'descriptor' in params['required']

    def test_get_children_schema(self):
        """get_children should have correct schema."""
        tools = get_tool_definitions()
        children_tool = [t for t in tools if t['function']['name'] == TOOL_GET_CHILDREN][0]

        func = children_tool['function']
        params = func['parameters']

        # Check parameters
        assert 'descriptor' in params['properties']
        desc_param = params['properties']['descriptor']

        assert desc_param['type'] == 'string'

        # Check required fields
        assert 'descriptor' in params['required']

    def test_descriptions_are_informative(self):
        """Tool descriptions should mention key information."""
        tools = get_tool_definitions()

        validate_tool = [t for t in tools if t['function']['name'] == TOOL_VALIDATE][0]
        assert 'FREE' in validate_tool['function']['description']
        assert 'does not count' in validate_tool['function']['description']

        parent_tool = [t for t in tools if t['function']['name'] == TOOL_GET_PARENT][0]
        assert 'REASONING' in parent_tool['function']['description']
        assert '3-call limit' in parent_tool['function']['description']

        children_tool = [t for t in tools if t['function']['name'] == TOOL_GET_CHILDREN][0]
        assert 'REASONING' in children_tool['function']['description']
        assert '3-call limit' in children_tool['function']['description']
