"""
Response Normalizer

Strips inline thinking/reasoning tags from LLM output before answer parsing.

When models are accessed via OpenRouter, reasoning content is already extracted
into message.reasoning (plain text) and removed from message.content — so
content arriving from OpenRouterClient is typically clean.

This normalizer acts as a defensive fallback for:
- Models accessed directly (not via OpenRouter)
- Edge cases where a model embeds <think> tags despite OpenRouter normalization
- Future models that may not follow the convention

Known inline tag formats:
  <think>...</think>       — Qwen3, Kimi K2, DeepSeek (native API)
  <thinking>...</thinking> — some open-source models
  <reasoning>...</reasoning> — some open-source models
"""

import re
from typing import Tuple, Optional


# Tags used by various reasoning models
_THINKING_PATTERNS = [
    r"<think>(.*?)</think>",
    r"<thinking>(.*?)</thinking>",
    r"<reasoning>(.*?)</reasoning>",
]


def normalize_response(content: str) -> Tuple[str, Optional[str]]:
    """
    Strip thinking/reasoning blocks from model response content.

    Args:
        content: Raw response text from the model

    Returns:
        (clean_content, thinking_content)
        - clean_content: response with thinking blocks removed and stripped
        - thinking_content: concatenated thinking blocks, or None if none found

    Example:
        >>> clean, thinking = normalize_response(
        ...     "<think>Option A seems wrong...</think>Therefore, I select (B)."
        ... )
        >>> clean
        'Therefore, I select (B).'
        >>> thinking[:10]
        'Option A s'
    """
    if not content:
        return content, None

    thinking_blocks = []
    clean = content

    for pattern in _THINKING_PATTERNS:
        matches = re.findall(pattern, clean, flags=re.DOTALL)
        if matches:
            thinking_blocks.extend(m.strip() for m in matches)
            clean = re.sub(pattern, "", clean, flags=re.DOTALL)

    clean = clean.strip()
    thinking = "\n\n".join(thinking_blocks) if thinking_blocks else None

    return clean, thinking
