"""
Graph Tools Module

Provides tool definitions and executor for LLM function calling.
Wraps CoffeeDescriptionGraph methods to expose them as LLM tools.
"""

from typing import Any, Dict

from .definitions import get_tool_definitions, TOOL_VALIDATE, TOOL_GET_PARENT, TOOL_GET_CHILDREN
from .executor import GraphToolExecutor
from .label_resolver import LabelResolver, normalize_label, DEFAULT_DISPLAY_CORRECTIONS
from .graph_render import render_graph, RENDER_FORMATS

LABEL_RESOLUTION_MODES = ("exact", "resolve")


def build_executor(graph, condition_config: Dict[str, Any]) -> GraphToolExecutor:
    """
    Build the executor a condition asks for.

    condition_config["label_resolution"]:
        "exact"   (default) — exact string match, as in the original experiment
        "resolve" — LabelResolver: layer labels, benchmark spellings, file misspellings,
                    separators, ring forms, clear typos, word forms (label_resolver.py)
    """
    mode = condition_config.get("label_resolution", "exact")
    if mode not in LABEL_RESOLUTION_MODES:
        raise ValueError(f"Unknown label_resolution '{mode}'; expected one of {LABEL_RESOLUTION_MODES}")
    resolver = LabelResolver.from_graph(graph) if mode == "resolve" else None
    return GraphToolExecutor(graph, resolver=resolver)


__all__ = [
    "get_tool_definitions",
    "GraphToolExecutor",
    "LabelResolver",
    "normalize_label",
    "DEFAULT_DISPLAY_CORRECTIONS",
    "build_executor",
    "render_graph",
    "RENDER_FORMATS",
    "LABEL_RESOLUTION_MODES",
    "TOOL_VALIDATE",
    "TOOL_GET_PARENT",
    "TOOL_GET_CHILDREN",
]
