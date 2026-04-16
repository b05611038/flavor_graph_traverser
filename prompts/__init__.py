"""
Prompt loader — reads prompt templates from ./prompts/*.txt

Each file is a plain-text template with optional {placeholders} for
str.format() substitution at runtime.

Usage:
    from prompts import load_prompt

    # Simple load (no placeholders)
    system = load_prompt("judge_system")

    # With placeholder substitution
    fmt = load_prompt("answer_format_single", options_list="A, B, C, or D")
"""

from pathlib import Path
from functools import lru_cache

_PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def _read_template(name: str) -> str:
    """Read and cache a prompt template file."""
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text().strip()


def load_prompt(name: str, **kwargs) -> str:
    """
    Load a prompt template by name, optionally substituting {placeholders}.

    Args:
        name: Filename without extension (e.g., "judge_system")
        **kwargs: Values for {placeholder} substitution

    Returns:
        Rendered prompt string

    Examples:
        >>> load_prompt("judge_system")
        'You are an expert coffee flavor evaluator...'
        >>> load_prompt("answer_format_single", options_list="A, B, C, or D")
        'You MUST end your response with exactly this format...'
    """
    template = _read_template(name)
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            # Template contains literal braces (e.g., JSON examples) —
            # fall back to manual replacement of known keys only
            result = template
            for key, value in kwargs.items():
                result = result.replace(f"{{{key}}}", str(value))
            return result
    return template
