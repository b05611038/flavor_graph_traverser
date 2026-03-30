"""
vLLM Client

Client for a local vLLM server (OpenAI-compatible API).
Used for end-to-end testing before running on OpenRouter.

Example:
    client = VLLMClient(
        model="openai/gpt-oss-20b",
        base_url="http://localhost:8000/v1"
    )
    response = client.query(messages=[...], tools=[...])
"""

import time
import requests
from typing import Dict, List, Optional, Any
from .base import BaseClient, Message, LLMResponse, UsageStats
from ..utils.response_normalizer import normalize_response


class VLLMClient(BaseClient):
    """
    Client for a local vLLM server.

    vLLM exposes an OpenAI-compatible /v1/chat/completions endpoint.
    No API key is required.

    Supports:
    - Function calling (tool_calls)
    - Automatic retries with exponential backoff
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8000/v1",
        timeout: int = 120,
        max_retries: int = 3,
        retry_backoff: List[int] = None,
        **kwargs
    ):
        super().__init__(model, **kwargs)
        self.base_url = base_url.rstrip("/")
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
        formatted_messages = self.format_messages(messages)

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        if tools:
            payload["tools"] = tools
            payload.setdefault("tool_choice", "auto")

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._make_request(payload)
                return self._parse_response(response)

            except requests.HTTPError as e:
                status_code = e.response.status_code
                if status_code == 429 or status_code >= 500:
                    wait_time = self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)]
                    print(f"Server error ({status_code}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    last_error = e
                    continue
                else:
                    raise

            except (requests.Timeout, requests.RequestException) as e:
                wait_time = self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)]
                print(f"Request error. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                last_error = e
                continue

        raise Exception(f"Max retries ({self.max_retries}) exceeded. Last error: {last_error}")

    def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url}/chat/completions"
        response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        choice = response["choices"][0]
        message = choice["message"]
        raw_content = message.get("content", "") or ""
        tool_calls = message.get("tool_calls")

        # vLLM surfaces reasoning-model thinking in message.reasoning
        # (same convention as OpenRouter). Capture it so we don't lose it.
        provider_thinking = message.get("reasoning") or message.get("reasoning_content")

        clean_content, tag_thinking = normalize_response(raw_content)

        # Provider-level reasoning takes priority over inline <think> tags
        thinking_content = provider_thinking or tag_thinking

        usage = None
        if "usage" in response:
            u = response["usage"]
            usage = UsageStats(
                input_tokens=u.get("prompt_tokens", 0),
                output_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
            )

        return LLMResponse(
            content=clean_content,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.get("finish_reason"),
            raw_response=response,
            thinking_content=thinking_content,
        )

    def supports_function_calling(self) -> bool:
        return True

    def list_models(self) -> List[str]:
        """List models available on the vLLM server."""
        url = f"{self.base_url}/models"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return [m["id"] for m in response.json().get("data", [])]
