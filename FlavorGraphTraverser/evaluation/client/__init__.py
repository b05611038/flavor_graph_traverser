"""
LLM Client Module

Provides abstract LLM client interface and implementations for:
- Ollama (local testing)
- OpenRouter (production API)

Example:
    from FlavorGraphTraverser.evaluation.client import create_client

    # For local testing
    client = create_client(
        client_type="ollama",
        model="tinyllama",
        base_url="http://localhost:11434"
    )

    # For production
    client = create_client(
        client_type="openrouter",
        model="anthropic/claude-sonnet-4.6"
    )

    # Query
    response = client.query(messages=[...], tools=[...])
"""

from .base import BaseClient, Message, LLMResponse, UsageStats
from .ollama import OllamaClient
from .openrouter import OpenRouterClient
from .vllm import VLLMClient
from typing import Optional, Dict, Any


def create_client(
    client_type: str,
    model: str,
    **kwargs
) -> BaseClient:
    """
    Factory function to create LLM clients.

    Args:
        client_type: Type of client ("ollama" or "openrouter")
        model: Model identifier
        **kwargs: Client-specific configuration

    Returns:
        BaseClient instance (OllamaClient or OpenRouterClient)

    Raises:
        ValueError: If client_type is not recognized

    Examples:
        # Ollama client
        client = create_client(
            client_type="ollama",
            model="tinyllama",
            base_url="http://localhost:11434"
        )

        # OpenRouter client
        client = create_client(
            client_type="openrouter",
            model="anthropic/claude-sonnet-4.6",
            api_key="sk-or-v1-..."
        )
    """
    client_type = client_type.lower()
    # Filter out None values so client class defaults are respected
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    if client_type == "ollama":
        return OllamaClient(model=model, **kwargs)

    elif client_type == "openrouter":
        return OpenRouterClient(model=model, **kwargs)

    elif client_type == "vllm":
        return VLLMClient(model=model, **kwargs)

    else:
        raise ValueError(
            f"Unknown client type: {client_type}. "
            f"Supported types: 'ollama', 'openrouter', 'vllm'"
        )


__all__ = [
    "BaseClient",
    "Message",
    "LLMResponse",
    "UsageStats",
    "OllamaClient",
    "OpenRouterClient",
    "VLLMClient",
    "create_client",
]
