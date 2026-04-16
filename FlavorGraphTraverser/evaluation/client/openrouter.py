"""
OpenRouter Client

Client for OpenRouter API. Provides access to multiple model providers
(OpenAI, Anthropic, Google, etc.) through a unified interface.
"""

import json
import os
import requests
import time
from typing import Dict, List, Optional, Any
from .base import BaseClient, Message, LLMResponse, UsageStats
from ..utils.response_normalizer import normalize_response


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
            model="anthropic/claude-sonnet-4.6",
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
        connect_timeout: int = 30,
        chunk_timeout: int = 120,
        max_retries: int = 3,
        retry_backoff: List[int] = None,
        **kwargs
    ):
        """
        Initialize OpenRouter client.

        Args:
            model: OpenRouter model ID (e.g., "anthropic/claude-sonnet-4.6")
            api_key: API key (if None, reads from environment)
            api_key_env: Environment variable name for API key
            base_url: OpenRouter API base URL
            site_url: Your site URL (for OpenRouter rankings)
            app_name: Your app name (for OpenRouter rankings)
            connect_timeout: Seconds to wait for initial TCP connection (default: 30)
            chunk_timeout: Seconds to wait between streamed chunks (default: 120).
                           With streaming each read is independently timed, so this
                           guards against a stuck connection mid-generation without
                           capping total response length.
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
        self.site_url = site_url or os.getenv("OPENROUTER_SITE_URL", "https://github.com/b05611038/flavor_graph_traverser")
        self.app_name = app_name or os.getenv("OPENROUTER_APP_NAME", "FlavorGraphTraverser")
        self.timeout = (connect_timeout, chunk_timeout)  # (connect, read) tuple for requests
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
            "include_reasoning": True,  # Surface reasoning tokens in message.reasoning
            **kwargs
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload.setdefault("tool_choice", "auto")

        # Make API request with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self._make_request(payload)

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

    def _make_request(self, payload: Dict[str, Any]) -> LLMResponse:
        """
        Make a single streaming API request and accumulate the response.

        Uses SSE streaming so the per-chunk read timeout (chunk_timeout) applies
        independently to each network read — a stuck connection is detected promptly
        regardless of total response length.

        Args:
            payload: Request payload (stream and stream_options are added here)

        Returns:
            LLMResponse assembled from accumulated stream chunks

        Raises:
            requests.HTTPError: If the HTTP status indicates an error
            requests.Timeout: If no chunk arrives within chunk_timeout seconds
        """
        stream_payload = {
            **payload,
            "stream": True,
            "stream_options": {"include_usage": True},  # usage in final chunk
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
        }

        url = f"{self.base_url}/chat/completions"
        response = requests.post(
            url,
            json=stream_payload,
            headers=headers,
            timeout=self.timeout,  # (connect_timeout, chunk_timeout) tuple
            stream=True,
        )
        response.raise_for_status()
        return self._parse_streaming_response(response)

    def _parse_streaming_response(self, response: requests.Response) -> LLMResponse:
        """
        Parse an SSE streaming response into an LLMResponse.

        Accumulates content, reasoning, and tool call deltas across chunks.
        Usage stats arrive in the final chunk via stream_options.

        Args:
            response: Streaming requests.Response object

        Returns:
            LLMResponse assembled from all chunks
        """
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        # tool_calls_map: index → {id, type, function: {name, arguments}}
        tool_calls_map: Dict[int, Dict] = {}
        finish_reason = None
        usage = None
        resolved_model = None  # Actual versioned model ID from API response

        for line in response.iter_lines():
            if not line:
                continue

            if isinstance(line, bytes):
                line = line.decode("utf-8")

            if not line.startswith("data: "):
                continue

            data_str = line[6:]  # strip "data: " prefix

            if data_str == "[DONE]":
                break

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # Capture resolved model ID from first chunk that has it
            if resolved_model is None and chunk.get("model"):
                resolved_model = chunk["model"]

            # Usage arrives in the final chunk when stream_options.include_usage=True
            if chunk.get("usage"):
                u = chunk["usage"]
                usage = UsageStats(
                    input_tokens=u.get("prompt_tokens", 0),
                    output_tokens=u.get("completion_tokens", 0),
                    total_tokens=u.get("total_tokens", 0),
                )

            choices = chunk.get("choices", [])
            if not choices:
                continue

            choice = choices[0]
            delta = choice.get("delta", {})

            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

            # Accumulate text content
            if delta.get("content"):
                content_parts.append(delta["content"])

            # Accumulate reasoning tokens (OpenRouter field: delta.reasoning)
            if delta.get("reasoning"):
                reasoning_parts.append(delta["reasoning"])

            # Accumulate tool call deltas
            # Each delta may carry id/name only in the first chunk for that index;
            # arguments arrive as successive partial strings to be concatenated.
            for tc_delta in delta.get("tool_calls", []):
                idx = tc_delta.get("index", 0)
                if idx not in tool_calls_map:
                    tool_calls_map[idx] = {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                tc = tool_calls_map[idx]
                if tc_delta.get("id"):
                    tc["id"] = tc_delta["id"]
                func = tc_delta.get("function", {})
                if func.get("name"):
                    tc["function"]["name"] += func["name"]
                if func.get("arguments"):
                    tc["function"]["arguments"] += func["arguments"]

        # Verify stream completed with usable data
        if not content_parts and not tool_calls_map and finish_reason is None:
            raise requests.ConnectionError(
                "Stream ended without content, tool calls, or finish_reason — "
                "connection may have been dropped prematurely"
            )

        # Assemble final content
        raw_content = "".join(content_parts)
        provider_thinking = "".join(reasoning_parts) or None

        # Defensively strip inline <think> tags as a fallback for non-standard models
        clean_content, tag_thinking = normalize_response(raw_content)
        thinking_content = provider_thinking or tag_thinking

        # Convert tool call map to ordered list, filtering out incomplete entries
        # (e.g. stream interrupted before function name arrived)
        tool_calls = None
        if tool_calls_map:
            complete = [
                tool_calls_map[i] for i in sorted(tool_calls_map)
                if tool_calls_map[i].get("function", {}).get("name")
            ]
            tool_calls = complete if complete else None

        return LLMResponse(
            content=clean_content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            raw_response={
                "streamed": True,
                "model": self.model,
                "finish_reason": finish_reason,
                "usage": {"prompt_tokens": usage.input_tokens, "completion_tokens": usage.output_tokens, "total_tokens": usage.total_tokens} if usage else None,
            },
            thinking_content=thinking_content,
            resolved_model=resolved_model,
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
