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
                    "No call limit. "
                    "The graph stores short descriptors (single words or short phrases like 'brown sugar', 'black tea'). "
                    "If an answer option is a multi-word phrase (e.g., 'winey cherry'), validate each component word separately (e.g., 'winey', 'cherry'). "
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
                    "This is a traversal call (limited budget, shared with get_children). "
                    "Only works on descriptors that exist in the graph — "
                    "returns an error if the descriptor is not found. "
                    "Returns a list of parent descriptor names. "
                    "If the descriptor has no parent (is a root category), returns an empty list. "
                    "Call this repeatedly to trace a path up to the root. "
                    "Example: get_parent('blueberry') → ['berry'], get_parent('berry') → ['fruity']."
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
                    "This is a traversal call (limited budget, shared with get_parent). "
                    "Only works on descriptors that exist in the graph — "
                    "returns an error if the descriptor is not found. "
                    "Returns a list of child descriptor names. "
                    "If the descriptor has no children (is a leaf node), returns an empty list. "
                    "Example: get_children('berry') → ['strawberry', 'blueberry', 'blackberry', 'raspberry']."
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
