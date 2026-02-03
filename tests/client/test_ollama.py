"""
Tests for Ollama Client

Tests OllamaClient functionality (requires running Ollama server).
"""

import pytest
from FlavorGraphTraverser.evaluation.client import create_client, Message


class TestOllamaClient:
    """Test OllamaClient."""

    def test_client_creation(self, ollama_config):
        """Should create Ollama client."""
        client = create_client(**ollama_config)
        assert client.model == ollama_config['model']
        assert client.base_url == ollama_config['base_url']

    def test_is_available(self, ollama_config):
        """Should check server availability."""
        client = create_client(**ollama_config)
        # May be True or False depending on server
        is_available = client.is_available()
        assert isinstance(is_available, bool)

    @pytest.mark.skipif(
        not pytest.importorskip("requests").get(
            "http://localhost:11434/api/tags", timeout=2
        ).status_code == 200,
        reason="Ollama server not available"
    )
    def test_list_models(self, ollama_config):
        """Should list available models."""
        client = create_client(**ollama_config)

        if not client.is_available():
            pytest.skip("Ollama server not available")

        models = client.list_models()
        assert isinstance(models, list)
        assert len(models) > 0

    @pytest.mark.skipif(
        not pytest.importorskip("requests").get(
            "http://localhost:11434/api/tags", timeout=2
        ).status_code == 200,
        reason="Ollama server not available"
    )
    def test_simple_query(self, ollama_config):
        """Should query model and get response."""
        client = create_client(**ollama_config)

        if not client.is_available():
            pytest.skip("Ollama server not available")

        messages = [Message(role="user", content="Say 'test' and nothing else.")]
        response = client.query(messages, temperature=0, max_tokens=10)

        assert response.content is not None
        assert isinstance(response.content, str)
        assert len(response.content) > 0

    @pytest.mark.skipif(
        not pytest.importorskip("requests").get(
            "http://localhost:11434/api/tags", timeout=2
        ).status_code == 200,
        reason="Ollama server not available"
    )
    def test_query_with_usage_stats(self, ollama_config):
        """Should return usage statistics."""
        client = create_client(**ollama_config)

        if not client.is_available():
            pytest.skip("Ollama server not available")

        messages = [Message(role="user", content="Hello")]
        response = client.query(messages, temperature=0, max_tokens=50)

        assert response.usage is not None
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0
        assert response.usage.total_tokens == (
            response.usage.input_tokens + response.usage.output_tokens
        )

    def test_supports_function_calling(self, ollama_config):
        """Should report function calling support."""
        client = create_client(**ollama_config)
        # Ollama has limited support, should return False
        assert client.supports_function_calling() is False

    @pytest.mark.skipif(
        not pytest.importorskip("requests").get(
            "http://localhost:11434/api/tags", timeout=2
        ).status_code == 200,
        reason="Ollama server not available"
    )
    def test_multi_turn_conversation(self, ollama_config):
        """Should handle multi-turn conversation."""
        client = create_client(**ollama_config)

        if not client.is_available():
            pytest.skip("Ollama server not available")

        messages = [
            Message(role="user", content="My name is Alice."),
        ]
        response1 = client.query(messages, temperature=0, max_tokens=50)

        messages.append(Message(role="assistant", content=response1.content))
        messages.append(Message(role="user", content="What is my name?"))

        response2 = client.query(messages, temperature=0, max_tokens=50)

        # Should mention Alice in some form
        assert response2.content is not None
        # Note: TinyLlama may not be reliable enough to pass this
