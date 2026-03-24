"""
Ollama Client

Client for local Ollama server. Used for debugging and testing
without incurring API costs.
"""

import requests
import json
from typing import Dict, List, Optional, Any
from .base import BaseClient, Message, LLMResponse, UsageStats
from ..utils.response_normalizer import normalize_response


class OllamaClient(BaseClient):
    """
    Client for Ollama API (local testing).

    Example:
        client = OllamaClient(
            model="tinyllama",
            base_url="http://localhost:11434"
        )
        response = client.query(messages=[...])
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: int = 60,
        **kwargs
    ):
        """
        Initialize Ollama client.

        Args:
            model: Model name (e.g., "tinyllama", "llama3")
            base_url: Ollama server URL
            timeout: Request timeout in seconds
            **kwargs: Additional configuration
        """
        super().__init__(model, **kwargs)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        **kwargs
    ) -> LLMResponse:
        """
        Query Ollama API.

        Args:
            messages: Conversation history
            tools: Optional tool definitions (Ollama has limited support)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            LLMResponse object

        Raises:
            requests.RequestException: If API call fails
        """
        # Format messages for Ollama API
        formatted_messages = self.format_messages(messages)

        # Build request payload
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        # Note: Ollama doesn't reliably support tools parameter
        # Silently ignore tools to maintain compatibility with abstract interface

        # Make API request
        url = f"{self.base_url}/api/chat"
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

        except requests.RequestException as e:
            raise Exception(f"Ollama API error: {e}")

        # Parse response
        message = result.get("message", {})
        raw_content = message.get("content", "") or ""
        tool_calls = message.get("tool_calls")

        # Strip inline thinking tags (for local reasoning models e.g. deepseek-r1, qwen3)
        clean_content, thinking_content = normalize_response(raw_content)

        # Extract usage stats (Ollama provides prompt/completion eval counts)
        usage = None
        if "prompt_eval_count" in result and "eval_count" in result:
            usage = UsageStats(
                input_tokens=result.get("prompt_eval_count", 0),
                output_tokens=result.get("eval_count", 0),
                total_tokens=result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
            )

        return LLMResponse(
            content=clean_content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=result.get("done_reason"),
            raw_response=result,
            thinking_content=thinking_content,
        )

    def supports_function_calling(self) -> bool:
        """
        Check function calling support.

        Returns:
            False for most Ollama models (experimental/limited support)
        """
        # Ollama has experimental function calling support in some models
        # For simplicity, return False and use text-based ReAct if needed
        return False

    def list_models(self) -> List[str]:
        """
        List available models on the Ollama server.

        Returns:
            List of model names

        Raises:
            requests.RequestException: If API call fails
        """
        url = f"{self.base_url}/api/tags"
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return [model["name"] for model in result.get("models", [])]

        except requests.RequestException as e:
            raise Exception(f"Failed to list Ollama models: {e}")

    def is_available(self) -> bool:
        """
        Check if Ollama server is available.

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
