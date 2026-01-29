"""Utility functions for type checking and data validation."""

from typing import Any, Dict, List, Optional, Tuple, Union


__all__ = [
    "boolean_check",
    "integer_check",
    "float_check",
    "string_check",
    "list_check",
    "dict_check",
    "lprint",
    "flatten_descriptions_connections",
]


def boolean_check(value: Any, name: str) -> bool:
    """
    Validate that a value is a boolean.

    Args:
        value: The value to check
        name: The name of the parameter (for error messages)

    Returns:
        The validated boolean value

    Raises:
        TypeError: If value is not a boolean
    """
    if not isinstance(value, bool):
        raise TypeError(f"Argument '{name}' must be a boolean, got {type(value).__name__}")
    return value


def integer_check(
    value: Any, name: str, valid_range: Optional[Tuple[Optional[int], Optional[int]]] = None
) -> int:
    """
    Validate that a value is an integer, optionally within a specified range.

    Args:
        value: The value to check
        name: The name of the parameter (for error messages)
        valid_range: Optional tuple of (min, max) values. None means no limit.

    Returns:
        The validated integer value

    Raises:
        TypeError: If value is not an integer
        ValueError: If value is outside the valid range
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"Argument '{name}' must be an integer, got {type(value).__name__}")

    if valid_range is not None:
        min_val, max_val = valid_range
        if min_val is not None and value < min_val:
            raise ValueError(f"Argument '{name}' must be >= {min_val}, got {value}")
        if max_val is not None and value > max_val:
            raise ValueError(f"Argument '{name}' must be <= {max_val}, got {value}")

    return value


def float_check(
    value: Any, name: str, valid_range: Optional[Tuple[Optional[float], Optional[float]]] = None
) -> float:
    """
    Validate that a value is a float, optionally within a specified range.

    Args:
        value: The value to check
        name: The name of the parameter (for error messages)
        valid_range: Optional tuple of (min, max) values. None means no limit.

    Returns:
        The validated float value

    Raises:
        TypeError: If value is not a float or int
        ValueError: If value is outside the valid range
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"Argument '{name}' must be a number, got {type(value).__name__}")

    value = float(value)

    if valid_range is not None:
        min_val, max_val = valid_range
        if min_val is not None and value < min_val:
            raise ValueError(f"Argument '{name}' must be >= {min_val}, got {value}")
        if max_val is not None and value > max_val:
            raise ValueError(f"Argument '{name}' must be <= {max_val}, got {value}")

    return value


def string_check(
    value: Any,
    name: str,
    valid_candidates: Optional[List[str]] = None,
    case_sensitive: bool = True,
) -> str:
    """
    Validate that a value is a string, optionally from a set of valid candidates.

    Args:
        value: The value to check
        name: The name of the parameter (for error messages)
        valid_candidates: Optional list of valid string values
        case_sensitive: Whether to perform case-sensitive matching

    Returns:
        The validated string value

    Raises:
        TypeError: If value is not a string
        ValueError: If value is not in valid_candidates
    """
    if not isinstance(value, str):
        raise TypeError(f"Argument '{name}' must be a string, got {type(value).__name__}")

    if valid_candidates is not None:
        if case_sensitive:
            if value not in valid_candidates:
                raise ValueError(
                    f"Argument '{name}' must be one of {valid_candidates}, got '{value}'"
                )
        else:
            value_lower = value.lower()
            candidates_lower = [c.lower() for c in valid_candidates]
            if value_lower not in candidates_lower:
                raise ValueError(
                    f"Argument '{name}' must be one of {valid_candidates}, got '{value}'"
                )

    return value


def list_check(
    value: Any, name: str, valid_candidates: Optional[List[Any]] = None
) -> List[Any]:
    """
    Validate that a value is a list, optionally with elements from valid candidates.

    Args:
        value: The value to check
        name: The name of the parameter (for error messages)
        valid_candidates: Optional list of valid element values

    Returns:
        The validated list

    Raises:
        TypeError: If value is not a list
        ValueError: If any element is not in valid_candidates
    """
    if not isinstance(value, list):
        raise TypeError(f"Argument '{name}' must be a list, got {type(value).__name__}")

    if valid_candidates is not None:
        for item in value:
            if item not in valid_candidates:
                raise ValueError(
                    f"Element '{item}' in '{name}' is not in valid candidates: {valid_candidates}"
                )

    return value


def dict_check(
    value: Any, name: str, necessary_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validate that a value is a dictionary, optionally with required keys.

    Args:
        value: The value to check
        name: The name of the parameter (for error messages)
        necessary_keys: Optional list of required dictionary keys

    Returns:
        The validated dictionary

    Raises:
        TypeError: If value is not a dictionary
        KeyError: If any necessary key is missing
    """
    if not isinstance(value, dict):
        raise TypeError(f"Argument '{name}' must be a dictionary, got {type(value).__name__}")

    if necessary_keys is not None:
        for key in necessary_keys:
            if key not in value:
                raise KeyError(f"Dictionary '{name}' is missing required key: '{key}'")

    return value


def lprint(text: str) -> None:
    """
    Print text with line wrapping support.

    Args:
        text: The text to print
    """
    print(text)


def flatten_descriptions_connections(
    connections: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Flatten a nested connection dictionary into a flat list.

    Args:
        connections: Dictionary mapping description names to lists of connections

    Returns:
        Flattened list of connection dictionaries

    Example:
        >>> connections = {
        ...     'floral': [
        ...         {'source': 'floral', 'target': 'rose', 'path_type': 'sub-category'}
        ...     ],
        ...     'fruity': [
        ...         {'source': 'fruity', 'target': 'berry', 'path_type': 'sub-category'}
        ...     ]
        ... }
        >>> flatten_descriptions_connections(connections)
        [{'source': 'floral', 'target': 'rose', 'path_type': 'sub-category'},
         {'source': 'fruity', 'target': 'berry', 'path_type': 'sub-category'}]
    """
    flattened_connections = []
    for descriptions_name in connections:
        connection_of_description = connections[descriptions_name]
        for conn in connection_of_description:
            flattened_connections.append(conn)

    return flattened_connections
