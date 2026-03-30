"""
ICL Tool Simulation

For models without native function calling support (deepseek/deepseek-v3.2,
meta-llama/llama-4-maverick, nvidia/nemotron-3-super-120b-a12b),
tools are described in the system prompt and tool calls are parsed from
model text output.

Format the model is instructed to use:
    TOOL_CALL: {"name": "get_parent", "args": {"descriptor": "jasmine"}}

Tool results are injected as:
    TOOL_RESULT: {"parents": ["floral"]}

If the model does not output a TOOL_CALL line, the turn is treated as a
direct answer attempt — parse_answer() runs on the text as normal. This
means ICL mode degrades gracefully: a model that ignores the tool format
just answers from its own knowledge, equivalent to the no_tool condition.
"""

import re
import json
from typing import Optional, Tuple, Dict, Any

from prompts import load_prompt

ICL_TOOL_INSTRUCTIONS = load_prompt("icl_tools")


def build_icl_system_prompt(base_system_prompt: str) -> str:
    """Append ICL tool instructions to the base system prompt."""
    return base_system_prompt.rstrip() + "\n\n" + ICL_TOOL_INSTRUCTIONS


def format_icl_tool_result(tool_name: str, result: Any) -> str:
    """Format a tool result as a text injection line."""
    return f"TOOL_RESULT: {json.dumps(result)}"


def parse_icl_tool_call(text: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Parse an ICL-style tool call from model response text.

    Looks for a line matching:
        TOOL_CALL: {"name": "...", "args": {...}}

    Returns:
        (tool_name, tool_args) if found and valid JSON
        (None, None) if not found or JSON is malformed

    Example:
        >>> name, args = parse_icl_tool_call(
        ...     'Let me check.\\nTOOL_CALL: {"name": "get_parent", "args": {"descriptor": "jasmine"}}'
        ... )
        >>> name
        'get_parent'
        >>> args
        {'descriptor': 'jasmine'}
    """
    if not text:
        return None, None

    # Match TOOL_CALL: followed by a JSON object with one level of nesting.
    # Pattern: { (non-brace chars | {non-brace chars})* }
    match = re.search(r"TOOL_CALL:\s*(\{(?:[^{}]|\{[^{}]*\})*\})", text)
    if not match:
        return None, None

    try:
        data = json.loads(match.group(1))
        name = data.get("name")
        args = data.get("args", {})
        if isinstance(name, str) and name:
            return name, args if isinstance(args, dict) else {}
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    return None, None
