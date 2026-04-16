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

import json
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
    - Streaming with per-chunk timeout (no SIGALRM needed)
    - Automatic retries with exponential backoff
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8000/v1",
        connect_timeout: int = 30,
        chunk_timeout: int = 90,
        max_retries: int = 1,
        retry_backoff: List[int] = None,
        **kwargs
    ):
        super().__init__(model, **kwargs)
        self.base_url = base_url.rstrip("/")
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
                return self._make_request(payload)

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
                print(f"Request timed out or failed. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                last_error = e
                continue

        raise Exception(f"Max retries ({self.max_retries}) exceeded. Last error: {last_error}")

    def _make_request(self, payload: Dict[str, Any]) -> LLMResponse:
        stream_payload = {
            **payload,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        headers = {"Content-Type": "application/json"}
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
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls_map: Dict[int, Dict] = {}
        finish_reason = None
        usage = None

        for line in response.iter_lines():
            if not line:
                continue

            if isinstance(line, bytes):
                line = line.decode("utf-8")

            if not line.startswith("data: "):
                continue

            data_str = line[6:]

            if data_str == "[DONE]":
                break

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

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

            if delta.get("content"):
                content_parts.append(delta["content"])

            if delta.get("reasoning"):
                reasoning_parts.append(delta["reasoning"])

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

        raw_content = "".join(content_parts)
        provider_thinking = "".join(reasoning_parts) or None

        clean_content, tag_thinking = normalize_response(raw_content)
        thinking_content = provider_thinking or tag_thinking

        # Filter out incomplete tool calls (e.g. stream interrupted before name arrived)
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
        )

    def supports_function_calling(self) -> bool:
        return True

    def list_models(self) -> List[str]:
        """List models available on the vLLM server."""
        url = f"{self.base_url}/models"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return [m["id"] for m in response.json().get("data", [])]
