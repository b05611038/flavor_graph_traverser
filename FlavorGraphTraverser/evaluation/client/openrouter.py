"""
OpenRouter Client

Client for OpenRouter API. Provides access to multiple model providers
(OpenAI, Anthropic, Google, etc.) through a unified interface.
"""

import os
import requests
import time
from typing import Dict, List, Optional, Any
from .base import BaseClient, Message, LLMResponse, UsageStats


class OpenRouterClient(BaseClient):
    """
    Client for OpenRouter API.

    Supports:
    - Multiple model providers (OpenAI, Anthropic, Google, xAI, Meta, etc.)
    - Function calling (for supported models)
    - Automatic retries with exponential backoff
    - Cost tracking via usage stats

    Example:
        client = OpenRouterClient(
            model="anthropic/claude-sonnet-4.5",
            api_key=os.getenv("OPENROUTER_API_KEY")
        )
        response = client.query(messages=[...], tools=[...])
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_key_env: str = "OPENROUTER_API_KEY",
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: Optional[str] = None,
        app_name: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3,
        retry_backoff: List[int] = None,
        **kwargs
    ):
        """
        Initialize OpenRouter client.

        Args:
            model: OpenRouter model ID (e.g., "anthropic/claude-sonnet-4.5")
            api_key: API key (if None, reads from environment)
            api_key_env: Environment variable name for API key
            base_url: OpenRouter API base URL
            site_url: Your site URL (for OpenRouter rankings)
            app_name: Your app name (for OpenRouter rankings)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            retry_backoff: Retry delays in seconds (default: [2, 4, 8])
            **kwargs: Additional configuration
        """
        super().__init__(model, **kwargs)

        # Get API key from argument or environment
        self.api_key = api_key or os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(
                f"OpenRouter API key not found. "
                f"Set {api_key_env} environment variable or pass api_key argument."
            )

        self.base_url = base_url.rstrip("/")
        self.site_url = site_url or "https://github.com/b05611038/flavor_graph_traverser"
        self.app_name = app_name or "FlavorGraphTraverser"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff or [2, 4, 8]

    def query(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        **kwargs
    ) -> LLMResponse:
        """
        Query OpenRouter API with automatic retries.

        Args:
            messages: Conversation history
            tools: Optional tool definitions for function calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model-specific parameters

        Returns:
            LLMResponse object

        Raises:
            Exception: If all retry attempts fail
        """
        # Format messages for OpenAI-compatible API
        formatted_messages = self.format_messages(messages)

        # Build request payload
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # Make API request with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._make_request(payload)
                return self._parse_response(response)

            except requests.HTTPError as e:
                status_code = e.response.status_code

                # Handle rate limiting (429)
                if status_code == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    wait_time = int(retry_after) if retry_after else self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)]
                    print(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    last_error = e
                    continue

                # Handle server errors (5xx)
                elif status_code >= 500:
                    wait_time = self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)]
                    print(f"Server error ({status_code}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    last_error = e
                    continue

                # Client errors (4xx) - don't retry
                else:
                    raise

            except requests.Timeout as e:
                wait_time = self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)]
                print(f"Request timeout. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                last_error = e
                continue

            except requests.RequestException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)]
                    print(f"Request failed. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise

        # All retries exhausted
        raise Exception(f"Max retries ({self.max_retries}) exceeded. Last error: {last_error}")

    def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a single API request.

        Args:
            payload: Request payload

        Returns:
            Response JSON

        Raises:
            requests.HTTPError: If request fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
        }

        url = f"{self.base_url}/chat/completions"
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """
        Parse OpenRouter API response.

        Args:
            response: API response JSON

        Returns:
            LLMResponse object
        """
        # Extract message
        choice = response["choices"][0]
        message = choice["message"]
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")

        # Extract usage stats
        usage = None
        if "usage" in response:
            usage_data = response["usage"]
            usage = UsageStats(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            )

        # Extract finish reason
        finish_reason = choice.get("finish_reason")

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            raw_response=response
        )

    def supports_function_calling(self) -> bool:
        """
        Check if this model supports function calling.

        Returns:
            True for most models (OpenRouter normalizes function calling)
        """
        # OpenRouter normalizes function calling across providers
        # Most models support it, but some have limited reliability
        # We'll trust OpenRouter's normalization
        return True

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Model info dict (pricing, context length, etc.)

        Raises:
            requests.RequestException: If API call fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        url = f"{self.base_url}/models/{self.model}"
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
