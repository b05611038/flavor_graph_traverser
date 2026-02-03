"""
Integration Tests - Client + Tools

Tests the integration of LLM clients with graph tools.
"""

import pytest
import json
from FlavorGraphTraverser.evaluation.client import create_client, Message
from FlavorGraphTraverser.evaluation.tools import (
    get_tool_definitions,
    GraphToolExecutor,
    TOOL_VALIDATE,
    TOOL_GET_PARENT
)


class TestClientToolsIntegration:
    """Integration tests for client and tools."""

    @pytest.mark.skipif(
        not pytest.importorskip("requests").get(
            "http://localhost:11434/api/tags", timeout=2
        ).status_code == 200,
        reason="Ollama server not available"
    )
    def test_query_with_tools_defined(self, ollama_config, graph_executor):
        """Should accept tool definitions (even if not used)."""
        client = create_client(**ollama_config)

        if not client.is_available():
            pytest.skip("Ollama server not available")

        tools = get_tool_definitions()
        messages = [Message(role="user", content="Hello")]

        # Should not raise error even though ollama doesn't use tools
        response = client.query(messages, tools=tools, temperature=0, max_tokens=50)
        assert response.content is not None

    def test_manual_tool_simulation(self, ollama_config, graph_executor, sample_descriptors):
        """Simulate tool calling workflow manually."""
        client = create_client(**ollama_config)

        if not client.is_available():
            pytest.skip("Ollama server not available")

        # Step 1: Ask about a descriptor
        descriptor = sample_descriptors['valid'][0]
        messages = [
            Message(
                role="user",
                content=f"I want to know the parent of '{descriptor}'. Should I use validate_descriptors first?"
            )
        ]

        response = client.query(messages, temperature=0, max_tokens=100)
        assert response.content is not None

        # Step 2: Simulate tool call - validate
        tool_result = graph_executor.validate_descriptors([descriptor])

        messages.append(Message(role="assistant", content=response.content))
        messages.append(
            Message(
                role="user",
                content=f"Tool result: {json.dumps(tool_result)}"
            )
        )

        # Step 3: Get response after tool result
        response2 = client.query(messages, temperature=0, max_tokens=100)
        assert response2.content is not None

    def test_tool_executor_with_valid_and_invalid(self, graph_executor, sample_descriptors):
        """Test executor handles both valid and invalid descriptors."""
        valid_desc = sample_descriptors['valid'][0]
        invalid_desc = sample_descriptors['invalid'][0]

        # Validate both
        result = graph_executor.validate_descriptors([valid_desc, invalid_desc])
        assert valid_desc in result['valid']
        assert invalid_desc in result['invalid']

        # Get parent of valid
        parent_result = graph_executor.get_parent(valid_desc)
        assert parent_result['error'] is None

        # Get parent of invalid
        invalid_result = graph_executor.get_parent(invalid_desc)
        assert invalid_result['error'] is not None
        assert 'not found' in invalid_result['error']

    def test_complete_tool_workflow(self, graph_executor, coffee_flavor_wheel_graph):
        """Test complete workflow: validate -> get_parent -> get_children."""
        # Find a descriptor with both parent and children
        target_desc = None
        for desc in coffee_flavor_wheel_graph.descriptions:
            parents = coffee_flavor_wheel_graph.parents_of_description(desc)
            children = coffee_flavor_wheel_graph.children_of_description(desc)
            if len(parents) > 0 and len(children) > 0:
                target_desc = desc
                break

        if target_desc is None:
            pytest.skip("No descriptor with both parent and children found")

        # Step 1: Validate
        validate_result = graph_executor.validate_descriptors([target_desc])
        assert target_desc in validate_result['valid']

        # Step 2: Get parent
        parent_result = graph_executor.get_parent(target_desc)
        assert parent_result['error'] is None
        assert len(parent_result['parents']) > 0

        # Step 3: Get children
        children_result = graph_executor.get_children(target_desc)
        assert children_result['error'] is None
        assert len(children_result['children']) > 0

    def test_batch_validation(self, graph_executor, sample_descriptors):
        """Test validating multiple descriptors at once."""
        all_descs = sample_descriptors['valid'][:5] + sample_descriptors['invalid'][:5]

        result = graph_executor.validate_descriptors(all_descs)

        # All valid descriptors should be in valid list
        for desc in sample_descriptors['valid'][:5]:
            assert desc in result['valid']

        # All invalid descriptors should be in invalid list
        for desc in sample_descriptors['invalid'][:5]:
            assert desc in result['invalid']

    def test_tool_definitions_format_for_openai(self):
        """Tool definitions should follow OpenAI function calling format."""
        tools = get_tool_definitions()

        for tool in tools:
            # Check OpenAI format
            assert tool['type'] == 'function'
            assert 'function' in tool

            func = tool['function']
            assert 'name' in func
            assert 'description' in func
            assert 'parameters' in func

            params = func['parameters']
            assert params['type'] == 'object'
            assert 'properties' in params
            assert 'required' in params

    def test_error_propagation(self, graph_executor):
        """Errors should be properly returned in tool results."""
        # Test with invalid descriptor
        result = graph_executor.get_parent('definitely_not_a_real_descriptor')

        assert 'error' in result
        assert result['error'] is not None
        assert 'not found' in result['error'].lower()
        assert result['parents'] is None

    def test_tool_result_structure(self, graph_executor, sample_descriptors):
        """Tool results should have consistent structure."""
        descriptor = sample_descriptors['valid'][0]

        # validate_descriptors
        validate_result = graph_executor.validate_descriptors([descriptor])
        assert 'valid' in validate_result
        assert 'invalid' in validate_result
        assert isinstance(validate_result['valid'], list)
        assert isinstance(validate_result['invalid'], list)

        # get_parent
        parent_result = graph_executor.get_parent(descriptor)
        assert 'descriptor' in parent_result
        assert 'parents' in parent_result
        assert 'error' in parent_result

        # get_children
        children_result = graph_executor.get_children(descriptor)
        assert 'descriptor' in children_result
        assert 'children' in children_result
        assert 'error' in children_result
