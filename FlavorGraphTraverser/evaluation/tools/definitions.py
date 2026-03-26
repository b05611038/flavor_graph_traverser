"""
Tool Definitions

Defines the function calling schemas for LLM tools.
Following OpenAI function calling format (compatible with OpenRouter).
"""

from typing import Dict, List, Any


# Tool name constants
TOOL_VALIDATE = "validate_descriptors"
TOOL_GET_PARENT = "get_parent"
TOOL_GET_CHILDREN = "get_children"


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get all tool definitions for function calling.

    Returns:
        List of tool definition dicts in OpenAI format

    Example:
        >>> tools = get_tool_definitions()
        >>> client.query(messages=[...], tools=tools)
    """
    return [
        {
            "type": "function",
            "function": {
                "name": TOOL_VALIDATE,
                "description": (
                    "Check if flavor descriptors exist in the flavor graph database. "
                    "Returns which descriptors are valid (exist) and which are invalid (don't exist). "
                    "No call limit — use freely. "
                    "Validation is optional: you can call get_parent or get_children directly without validating first. "
                    "If a descriptor is not in the graph, try querying the answer option labels "
                    "(e.g., 'fruity', 'spices', 'floral') or known category names directly. "
                    "Maximum 10 descriptors per call."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "descriptors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of flavor descriptor names to validate (max 10)",
                            "maxItems": 10,
                            "minItems": 1,
                        }
                    },
                    "required": ["descriptors"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_GET_PARENT,
                "description": (
                    "Get the parent node(s) of a flavor descriptor in the hierarchy. "
                    "Counts toward your reasoning call budget (shared with get_children). "
                    "Returns a list of parent descriptor names. "
                    "If the descriptor has no parent (is a root category), returns an empty list. "
                    "Call this repeatedly to trace a path up to the root. "
                    "Example: get_parent('rose') → ['floral'], get_parent('floral') → [] (root)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "descriptor": {
                            "type": "string",
                            "description": "The flavor descriptor name to query",
                        }
                    },
                    "required": ["descriptor"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_GET_CHILDREN,
                "description": (
                    "Get the child node(s) of a flavor descriptor in the hierarchy. "
                    "Counts toward your reasoning call budget (shared with get_parent). "
                    "Returns a list of child descriptor names. "
                    "If the descriptor has no children (is a leaf node), returns an empty list. "
                    "Example: get_children('floral') → ['rose', 'jasmine', 'lavender']."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "descriptor": {
                            "type": "string",
                            "description": "The flavor descriptor name to query",
                        }
                    },
                    "required": ["descriptor"],
                },
            },
        },
    ]


def get_validation_tool() -> Dict[str, Any]:
    """Get only the validation tool definition."""
    tools = get_tool_definitions()
    return [t for t in tools if t["function"]["name"] == TOOL_VALIDATE][0]


def get_reasoning_tools() -> List[Dict[str, Any]]:
    """Get only the reasoning tool definitions (get_parent, get_children)."""
    tools = get_tool_definitions()
    return [t for t in tools if t["function"]["name"] in [TOOL_GET_PARENT, TOOL_GET_CHILDREN]]
