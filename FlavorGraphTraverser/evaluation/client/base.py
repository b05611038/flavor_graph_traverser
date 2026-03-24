"""
Base LLM Client

Abstract base class for LLM clients. Defines the interface that all
client implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class Message:
    """Represents a single message in the conversation."""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # For tool results
    thinking_content: Optional[str] = None  # Reasoning tokens (reasoning models only)


@dataclass
class UsageStats:
    """Token usage statistics for a single API call."""
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    """
    Response from an LLM API call.

    Attributes:
        content: The text response from the model (thinking blocks already stripped)
        tool_calls: List of tool calls made (if any)
        usage: Token usage statistics
        finish_reason: Why the model stopped ("stop", "tool_calls", "length", etc.)
        raw_response: Original API response (for debugging)
        thinking_content: Chain-of-thought from reasoning models (Qwen3, DeepSeek, Grok).
                          Extracted from <think> tags or provider-specific fields.
                          None for non-reasoning models.
    """
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[UsageStats] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    thinking_content: Optional[str] = None


class BaseClient(ABC):
    """
    Abstract base class for LLM clients.

    All client implementations (OllamaClient, OpenRouterClient) must
    inherit from this class and implement the abstract methods.
    """

    def __init__(self, model: str, **kwargs):
        """
        Initialize the client.

        Args:
            model: Model identifier (e.g., "tinyllama", "anthropic/claude-sonnet-4.5")
            **kwargs: Additional client-specific configuration
        """
        self.model = model
        self.config = kwargs

    @abstractmethod
    def query(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        **kwargs
    ) -> LLMResponse:
        """
        Send a query to the LLM and get a response.

        Args:
            messages: Conversation history (list of Message objects)
            tools: Optional tool definitions for function calling
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters

        Returns:
            LLMResponse object containing the model's response

        Raises:
            Exception: If the API call fails
        """
        pass

    @abstractmethod
    def supports_function_calling(self) -> bool:
        """
        Check if this model supports function calling.

        Returns:
            True if function calling is supported, False otherwise
        """
        pass

    def format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert Message objects to API-compatible format.

        Args:
            messages: List of Message objects

        Returns:
            List of message dicts in API format
        """
        formatted = []
        for msg in messages:
            msg_dict = {
                "role": msg.role,
                "content": msg.content
            }

            # Add tool-specific fields if present
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            if msg.name:
                msg_dict["name"] = msg.name

            formatted.append(msg_dict)

        return formatted

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model='{self.model}')"
