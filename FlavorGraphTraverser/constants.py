"""Constants and default configurations for flavor graphs."""

from typing import Dict


__all__ = [
    "description_graph_connections",
    "description_hierarchy_connections",
    "DEFAULT_CONNECTION_DISTANCES",
]


# Valid connection types for description graphs
description_graph_connections = [
    "sub-category",
    "cross-descriptions",
    "synonym",
    "related",
]

# Valid connection types for hierarchies
description_hierarchy_connections = [
    "sub-category",
    "cross-descriptions",
]

# Default weights for different connection types
# Used for weighted shortest path calculations
DEFAULT_CONNECTION_DISTANCES: Dict[str, Dict[str, float]] = {
    "forward": {
        "sub-category": 1.0,
        "cross-descriptions": 10.0,
        "synonym": 0.5,
        "related": 5.0,
    },
    "reverse": {
        "sub-category": 1.0,
        "cross-descriptions": 10.0,
        "synonym": 0.5,
        "related": 5.0,
    },
}
