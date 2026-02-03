"""
Tests for Base Client

Tests the abstract base client interface.
"""

import pytest
from FlavorGraphTraverser.evaluation.client import BaseClient, Message, LLMResponse, UsageStats


class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        """Should create message with required fields."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None

    def test_message_with_tool_calls(self):
        """Should create message with tool calls."""
        tool_calls = [{"name": "test", "args": {}}]
        msg = Message(role="assistant", content="", tool_calls=tool_calls)
        assert msg.tool_calls == tool_calls

    def test_message_with_tool_result(self):
        """Should create tool result message."""
        msg = Message(
            role="tool",
            content="result",
            tool_call_id="call_123",
            name="test_tool"
        )
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"
        assert msg.name == "test_tool"


class TestUsageStats:
    """Test UsageStats dataclass."""

    def test_usage_stats_creation(self):
        """Should create usage stats."""
        stats = UsageStats(input_tokens=100, output_tokens=50, total_tokens=150)
        assert stats.input_tokens == 100
        assert stats.output_tokens == 50
        assert stats.total_tokens == 150


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_response_creation(self):
        """Should create response with content."""
        response = LLMResponse(content="Hello")
        assert response.content == "Hello"
        assert response.tool_calls is None
        assert response.usage is None

    def test_response_with_usage(self):
        """Should create response with usage stats."""
        usage = UsageStats(input_tokens=100, output_tokens=50, total_tokens=150)
        response = LLMResponse(content="Hello", usage=usage)
        assert response.usage == usage

    def test_response_with_tool_calls(self):
        """Should create response with tool calls."""
        tool_calls = [{"name": "test", "args": {}}]
        response = LLMResponse(content="", tool_calls=tool_calls)
        assert response.tool_calls == tool_calls


class TestBaseClient:
    """Test BaseClient abstract class."""

    def test_cannot_instantiate_directly(self):
        """Should not be able to instantiate abstract class."""
        with pytest.raises(TypeError):
            BaseClient(model="test")

    def test_format_messages(self):
        """Should format messages for API."""
        # Create a concrete implementation for testing
        class TestClient(BaseClient):
            def query(self, messages, tools=None, temperature=0, max_tokens=1024, **kwargs):
                pass

            def supports_function_calling(self):
                return True

        client = TestClient(model="test")

        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi", tool_calls=[{"name": "test"}]),
            Message(role="tool", content="result", tool_call_id="123", name="test")
        ]

        formatted = client.format_messages(messages)

        assert len(formatted) == 3
        assert formatted[0] == {"role": "user", "content": "Hello"}
        assert formatted[1]["role"] == "assistant"
        assert formatted[1]["tool_calls"] == [{"name": "test"}]
        assert formatted[2]["role"] == "tool"
        assert formatted[2]["tool_call_id"] == "123"
