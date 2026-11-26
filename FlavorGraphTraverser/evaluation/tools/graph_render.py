"""
Graph Renderer

Serializes the whole tool graph as text so it can be placed in the prompt
(graph_in_context condition).

Node names are written as stored in the graph (including layer-qualified names
such as "floral (inner layer)"), optionally with name_map applied — the
graph_in_context condition can show corrected spellings of tool-graph file
defects ("graphfruit" -> "grapefruit") via `graph_names: corrected`. The wording of the surrounding prompt lives in configs/conditions.yaml.
"""

import json
from typing import Dict, List, Optional

RENDER_FORMATS = ("json", "tree", "edges")


def _children(graph, node: str) -> List[str]:
    return list(graph.children_of_description(node))


def render_tree(graph, indent: str = "  ", name_map: Optional[Dict[str, str]] = None) -> str:
    """
    Indented outline in depth-first pre-order (siblings in stored order), one node
    per line, root categories at depth 0. Each root-to-leaf chain and each subtree
    is contiguous, which suits the ancestor/path/LCA tasks.

        fruity
          berry
            blackberry
            ...
    """
    lines: List[str] = []

    def walk(node: str, depth: int, seen: set) -> None:
        if node in seen:  # the renderers assume a tree; a repeated node would be dropped
            raise ValueError(f"Node '{node}' reached twice: the graph is not a tree")
        seen.add(node)
        lines.append(f"{indent * depth}{(name_map or {}).get(node, node)}")
        for child in _children(graph, node):
            walk(child, depth + 1, seen)

    seen: set = set()
    for top in _children(graph, graph.root):
        walk(top, 0, seen)
    return "\n".join(lines)


def render_edges(graph, name_map: Optional[Dict[str, str]] = None) -> str:
    """One '(parent, child)' line per edge (root edges omitted), breadth-first.

    Pair notation follows NLGraph (Wang et al., NeurIPS 2023). '>' is deliberately
    avoided: T1.4 options are written 'root > ... > leaf', and a serialization that
    resembles the answer format would let a model answer by string matching.
    """
    lines: List[str] = []
    queue = list(_children(graph, graph.root))
    seen = set(queue)
    while queue:
        node = queue.pop(0)
        for child in _children(graph, node):
            nm = name_map or {}
            lines.append(f"({nm.get(node, node)}, {nm.get(child, child)})")
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return "\n".join(lines)


def render_json(graph, name_map: Optional[Dict[str, str]] = None) -> str:
    """
    Nested JSON object, pretty-printed with 2-space indentation: each key is a node and
    its value is an object holding that node's children; a node without children maps
    to {} (one rule for every node, since some parents have both leaf and non-leaf
    children). The 9 top-level keys are the top-level categories; the root is omitted.

        {
          "fruity": {
            "berry": {
              "blackberry": {},
              ...

    JSON is the encoding the graph tools return their results in, so a graph_in_context
    condition using this format differs from the tool conditions in access mode, not in
    how graph content is written.
    """
    nm = name_map or {}

    def build(node: str, seen: set) -> dict:
        out: dict = {}
        for child in _children(graph, node):
            if child in seen:  # the renderers assume a tree; a repeated node would be dropped
                raise ValueError(f"Node '{child}' reached twice: the graph is not a tree")
            seen.add(child)
            key = nm.get(child, child)
            if key in out:
                raise ValueError(f"Duplicate child name '{key}' under '{node}'")
            out[key] = build(child, seen)
        return out

    return json.dumps(build(graph.root, set()), indent=2, ensure_ascii=False)


def render_graph(graph, fmt: str, name_map: Optional[Dict[str, str]] = None) -> str:
    """Render the graph in one of RENDER_FORMATS; name_map renames nodes for display."""
    if fmt == "json":
        return render_json(graph, name_map=name_map)
    if fmt == "tree":
        return render_tree(graph, name_map=name_map)
    if fmt == "edges":
        return render_edges(graph, name_map=name_map)
    raise ValueError(f"Unknown graph render format '{fmt}'; expected one of {RENDER_FORMATS}")
