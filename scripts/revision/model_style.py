"""Marker, colour and short name of each evaluated model, shared by the figure panels."""

# short name: (marker, colour)
MODEL_STYLE = {
    "Gemini 3 flash preview": ("o", "#1f77b4"),
    "GPT-OSS 120B": ("s", "#d62728"),
    "Sonnet 4.6": ("^", "#2ca02c"),
    "GPT-5.4": ("D", "#9467bd"),
    "Kimi K2.5": ("v", "#8c564b"),
    "Qwen 3.5 397B": ("P", "#e377c2"),
    "Mistral Medium 3.5": ("X", "#7f7f7f"),
    "Llama 4 Maverick": ("h", "#bcbd22"),
    "Grok 4.20": ("<", "#17becf"),
    "Nemotron 3 Super": ("p", "#ff7f0e"),
    "DeepSeek V3.2": ("*", "#393b79"),
}

# shorter labels for tight legends
DISPLAY = {"Mistral Medium 3.5": "Mistral Med. 3.5"}


def label(short):
    return DISPLAY.get(short, short)


# OpenRouter model ID -> short name
M2S = {
    "anthropic/claude-sonnet-4.6": "Sonnet 4.6",
    "google/gemini-3-flash-preview": "Gemini 3 flash preview",
    "openai/gpt-5.4": "GPT-5.4",
    "openai/gpt-oss-120b": "GPT-OSS 120B",
    "x-ai/grok-4.20": "Grok 4.20",
    "moonshotai/kimi-k2.5": "Kimi K2.5",
    "nvidia/nemotron-3-super-120b-a12b": "Nemotron 3 Super",
    "qwen/qwen3.5-397b-a17b": "Qwen 3.5 397B",
    "deepseek/deepseek-v3.2": "DeepSeek V3.2",
    "meta-llama/llama-4-maverick": "Llama 4 Maverick",
    "mistralai/mistral-medium-3-5": "Mistral Medium 3.5",
}
