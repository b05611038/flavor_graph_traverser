#!/usr/bin/env python3
"""
Fetch the resolved (versioned) model ID from OpenRouter for each model
used in the benchmark, and save to data/resolved_models.json.

Usage:
    OPENROUTER_API_KEY=sk-... python scripts/fetch_resolved_models.py
"""

import json
import os
import sys
import requests
from pathlib import Path

# Load .env if present
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

MODELS = [
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.4",
    "openai/gpt-oss-120b",
    "google/gemini-3-flash-preview",
    "mistralai/mistral-medium-3.1",
    "nvidia/nemotron-3-super-120b-a12b",
    "x-ai/grok-4.1-fast",
    "deepseek/deepseek-v3.2",
    "meta-llama/llama-4-maverick",
    "moonshotai/kimi-k2.5",
    "qwen/qwen3.5-397b-a17b",
]

OUTPUT = Path("data/resolved_models.json")


def fetch_resolved(model: str, api_key: str) -> str | None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 16,
        "stream": True,
        "stream_options": {"include_usage": False},
    }
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=(10, 30),
        )
        if not resp.ok:
            print(f"  HTTP {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
            return None
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode() if isinstance(line, bytes) else line
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                if chunk.get("model"):
                    return chunk["model"]
            except json.JSONDecodeError:
                continue
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", help="Only fetch these model IDs (substring match)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # Load existing results if any
    results = {}
    if OUTPUT.exists():
        results = json.loads(OUTPUT.read_text())

    models = MODELS
    if args.models:
        models = [m for m in MODELS if any(f in m for f in args.models)]

    for model in models:
        print(f"Querying {model} ...", end=" ", flush=True)
        resolved = fetch_resolved(model, api_key)
        results[model] = resolved
        print(resolved or "FAILED")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
