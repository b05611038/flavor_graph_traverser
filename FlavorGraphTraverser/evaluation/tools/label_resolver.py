"""
Label Resolver

Maps descriptor strings issued by a model onto canonical tool-graph node names.

Why this exists:
The Coffee Taster's Flavor Wheel repeats some labels across rings — "floral" and
"green/vegetative" each appear in the inner and the middle ring. The tool graph
disambiguates them with layer-qualified node names such as "floral (inner layer)",
which the model is never told about. A bare query such as validate_descriptors(["floral"])
therefore returned "invalid" in the original experiment.

The resolver removes that implementation artifact:
  1. Layer aliases: every node "<label> (<ring> layer)" makes the bare "<label>"
     resolve to the innermost-ring node carrying that label (inner > middle > outer).
     The bare label names the top-level category, which is also how the benchmark
     (system) graph names it.
  2. Extra aliases (DEFAULT_EXTRA_ALIASES), each tied to a defect of the tool-graph file:
     - benchmark-graph spellings: "green/vegetable" (the system-graph root) and
       "whisky" (the tool graph has "whiskey");
     - misspelled wheel terms in the tool graph ("graphfruit", "mapple syrup");
     - spelling variants of the layered green/vegetative label seen in transcripts.
  3. Surface normalization: case, surrounding/repeated whitespace, "_" vs " "
     (the tool graph stores "black_tea") and spaces around "/" ("green/ vegetative").
  4. Separator fallback: if nothing above matches, the separators space, "_", "-" and
     "/" are treated as the same (and may be missing), so "blacktea", "black-tea",
     "hay like", "musty earthy", "green vegetable" and "floral(inner layer)" resolve. Other punctuation is not ignored: "}nutty"
     (a malformed call) stays unresolved. A compact key shared by two
     different nodes is dropped (never guessed); the 111 tool-graph nodes have none.

  5. Word forms: a reviewed list of related forms models
     used ("fruit" -> "fruity", "wood" -> "woody", DEFAULT_WORD_FORMS) and the
     singular/plural of every node ("spice" -> "spices", "peanut" -> "peanuts").

Deliberately NOT resolved:
  - "green" alone (ambiguous: also part of "dark green");
  - invented ring names such as "floral (outer layer)" (no such node in the wheel);
  - different words that merely look alike ("pea"/"pear", "acid"/"acrid"); there is no
    fuzzy matching;
  - compound phrases ("blueberry jam"): the prompt tells models these do not count;
  - "roast" (ambiguous: "roasted" or "brown, roast").

Exact node names always resolve to themselves, so a resolver-backed executor gives
identical answers to the original executor for every query that already matched.
"""

import re
from typing import Dict, Iterable, Optional


# Ring order used to pick the canonical node for a bare layered label.
LAYER_ORDER = ("inner", "middle", "outer")
_LAYER_RE = re.compile(r"^(?P<label>.+?)\s*\((?P<ring>inner|middle|outer) layer\)$")

# Aliases that layer stripping and surface normalization do not cover.
# Targets must be existing tool-graph nodes (aliases with missing targets are ignored).
DEFAULT_EXTRA_ALIASES: Dict[str, str] = {
    # Benchmark (system) graph spellings that differ from the tool graph
    "green/vegetable": "green/vegetative (inner layer)",
    "whisky": "whiskey",
    # Spelling variants of the layered label issued by models in the original run
    "green vegetative": "green/vegetative (inner layer)",
    "green/vegetal": "green/vegetative (inner layer)",
    # Misspellings in the tool-graph file (wheel: "Grapefruit", "Maple Syrup")
    "grapefruit": "graphfruit",
    "maple syrup": "mapple syrup",
    # Same-word spelling variants / typos models issued in the original run (word forms
    # such as "fruit"/"fruity" are in DEFAULT_WORD_FORMS below)
    "smokey": "smoky",
    "winy": "winey",
    "animallic": "animalic",
}

# Word forms of wheel terms: models query a
# related form ("fruit" for the wheel's "fruity"). Reviewed list built from the original
# run's unresolved queries (scripts/revision/word_form_candidates.py). Excluded as
# ambiguous: "roast" (roasted vs. "brown, roast"). Singular/plural pairs are generated
# for every node (WORD_FORM_PLURALS) and need no entry here.
DEFAULT_WORD_FORMS: Dict[str, str] = {
    "fruit": "fruity", "wine": "winey", "bean": "beany", "animal": "animalic",
    "wood": "woody", "woodsy": "woody", "nut": "nutty", "smoke": "smoky",
    "malty": "malt", "malted": "malt", "paper": "papery", "skunk": "skunky",
    "chocolatey": "chocolate", "chocolaty": "chocolate", "soury": "sour",
    "grainy": "grain", "sweetness": "sweet", "peppery": "pepper", "ash": "ashy",
    "salt": "salty", "ferment": "fermented", "phenol": "phenolic", "tobaccoy": "tobacco",
}


# Display corrections for node names that are defects of the tool-graph file.
# With a resolver, tool outputs show the corrected name; queries with either the
# stored or the corrected spelling resolve to the node. Layer-qualified names are
# NOT corrected: the layering is real wheel structure.
DEFAULT_DISPLAY_CORRECTIONS: Dict[str, str] = {
    "graphfruit": "grapefruit",
    "mapple syrup": "maple syrup",
    "black_tea": "black tea",
}

# Category of each extra alias (for reporting which kind of fix changed a lookup)
ALIAS_CATEGORY: Dict[str, str] = {
    "green/vegetable": "benchmark_spelling",
    "whisky": "benchmark_spelling",
    "green vegetative": "layer_label_variant",
    "green/vegetal": "layer_label_variant",
    "grapefruit": "tool_graph_misspelling",
    "maple syrup": "tool_graph_misspelling",
    "smokey": "query_spelling_variant",
    "winy": "query_spelling_variant",
    "animallic": "query_spelling_variant",
    **{a: "word_form" for a in DEFAULT_WORD_FORMS},
}

_SLASH_RE = re.compile(r"\s*/\s*")
_SEPARATOR_RE = re.compile(r"[\s_\-/]+")


def normalize_label(text: str) -> str:
    """Surface normalization: lowercase, '_' -> ' ', collapse whitespace, no spaces around '/'."""
    return _SLASH_RE.sub("/", " ".join(text.replace("_", " ").lower().split()))


def _number_forms(key: str) -> list:
    """Singular/plural counterparts of the last word of a normalized label."""
    if re.search(r"[^aeiou]ies$", key):
        return [key[:-3] + "y"]                       # berries -> berry
    if re.search(r"(s|x|z|ch|sh)es$", key):
        return [key[:-2]]                             # peaches -> peach
    if key.endswith("s") and not key.endswith("ss"):
        return [key[:-1]]                             # spices -> spice
    if re.search(r"[^aeiou]y$", key):
        return [key[:-1] + "ies"]                     # berry -> berries
    if re.search(r"(s|x|z|ch|sh)$", key):
        return [key + "es"]
    return [key + "s"]


def compact_label(text: str) -> str:
    """Lowercase with the separators space, "_", "-" and "/" removed
    ("Black_Tea", "black-tea" -> "blacktea"; "musty earthy" -> "mustyearthy").
    Other punctuation (parentheses, stray JSON characters) is kept."""
    return _SEPARATOR_RE.sub("", text.lower())


class LabelResolver:
    """
    Resolve model-issued descriptor strings to canonical graph node names.

    Example:
        >>> r = LabelResolver(["floral (inner layer)", "floral (middle layer)", "rose", "black_tea"])
        >>> r.resolve("floral")
        'floral (inner layer)'
        >>> r.resolve("Black tea")
        'black_tea'
        >>> r.resolve("rose")
        'rose'
        >>> r.resolve("blueberry jam") is None
        True
    """

    def __init__(
        self,
        nodes: Iterable[str],
        extra_aliases: Optional[Dict[str, str]] = None,
        display_corrections: Optional[Dict[str, str]] = None,
        word_forms: Optional[Dict[str, str]] = None,
    ):
        self.nodes = set(nodes)
        corrections = DEFAULT_DISPLAY_CORRECTIONS if display_corrections is None else display_corrections
        self.display_corrections: Dict[str, str] = {
            n: d for n, d in corrections.items() if n in self.nodes
        }
        self._index: Dict[str, str] = {}

        # 1. Every node under its normalized form.
        for node in sorted(self.nodes):
            self._add(normalize_label(node), node)

        # 2. Bare label -> innermost layered node.
        layered: Dict[str, list] = {}
        for node in self.nodes:
            m = _LAYER_RE.match(node)
            if m:
                layered.setdefault(normalize_label(m.group("label")), []).append(
                    (LAYER_ORDER.index(m.group("ring")), node)
                )
        self.layer_aliases: Dict[str, str] = {
            label: min(entries)[1] for label, entries in sorted(layered.items())
        }
        for label, node in self.layer_aliases.items():
            self._add(label, node)
        # Ring written without parentheses or without "layer":
        # "floral middle layer", "floral (middle)", "floral middle" -> "floral (middle layer)"
        for node in self.nodes:
            m = _LAYER_RE.match(node)
            if m:
                label, ring = normalize_label(m.group("label")), m.group("ring")
                for variant in (f"{label} {ring} layer", f"{label} ({ring})", f"{label} {ring}"):
                    self._add(variant, node)

        # 3. Extra aliases (only those whose target exists in this graph).
        aliases = dict(DEFAULT_EXTRA_ALIASES if extra_aliases is None else extra_aliases)
        aliases.update(DEFAULT_WORD_FORMS if word_forms is None else word_forms)
        self.extra_aliases: Dict[str, str] = {
            normalize_label(a): t for a, t in aliases.items() if t in self.nodes
        }
        for alias, node in self.extra_aliases.items():
            self._add(alias, node)

        # Singular/plural of every name above (nodes and aliases, so "fruits" -> "fruity"):
        # consonant+"y" <-> "ies" (berry/berries), "-es" after s/x/z/ch/sh, else "-s".
        # A form already taken is skipped; a form two names would share is dropped.
        candidates: Dict[str, set] = {}
        for key, node in sorted(self._index.items()):
            if key.startswith("root:") or "layer" in key:
                continue
            for form in _number_forms(key):
                if len(form.split(" ")[-1]) >= 3 and form not in self._index:
                    candidates.setdefault(form, set()).add(node)
        self.plural_aliases: Dict[str, str] = {f: next(iter(n)) for f, n in candidates.items() if len(n) == 1}
        self.ambiguous_plural_forms = sorted(f for f, n in candidates.items() if len(n) > 1)
        for form, node in self.plural_aliases.items():
            self._index[form] = node

        # 4. Compact fallback over every key above; ambiguous compact keys are dropped.
        compact: Dict[str, set] = {}
        for key, node in self._index.items():
            compact.setdefault(compact_label(key), set()).add(node)
        self._compact_index: Dict[str, str] = {
            k: next(iter(v)) for k, v in compact.items() if k and len(v) == 1
        }
        self.ambiguous_compact_keys = sorted(k for k, v in compact.items() if len(v) > 1)

    def _add(self, key: str, node: str) -> None:
        existing = self._index.get(key)
        if existing is not None and existing != node:
            raise ValueError(
                f"Ambiguous label '{key}': maps to both '{existing}' and '{node}'"
            )
        self._index[key] = node

    def display(self, node: str) -> str:
        """Name to show the model for a canonical node (corrects file misspellings)."""
        return self.display_corrections.get(node, node)

    def classify(self, descriptor) -> Optional[str]:
        """
        Which fix makes `descriptor` resolve, or None if it is an exact node name
        or does not resolve at all. One of: layer_label, layer_label_variant,
        benchmark_spelling, tool_graph_misspelling, query_spelling_variant, word_form,
        surface_normalization.
        """
        if not isinstance(descriptor, str) or descriptor in self.nodes or self.resolve(descriptor) is None:
            return None
        key = normalize_label(descriptor)
        if key not in self._index:  # reached through the compact fallback
            key = next((k for k in self._index if compact_label(k) == compact_label(descriptor)), key)
        if key in self.layer_aliases:
            return "layer_label"
        if key in self.extra_aliases:
            return ALIAS_CATEGORY.get(key, "extra_alias")
        if key in self.plural_aliases:
            return "word_form"
        return "surface_normalization"

    # Alias kinds that name a node differently from the graph in the benchmark's own
    # vocabulary (questions say "floral", "green/vegetable"). Model-typed variants
    # ("green vegetative") and file misspellings (shown corrected) are not included.
    QUESTION_VOCABULARY_ALIASES = ("layer_label", "benchmark_spelling")

    def alias_table(self, categories: Iterable[str] = QUESTION_VOCABULARY_ALIASES) -> Dict[str, str]:
        """
        {alias: displayed node name} for the selected alias categories — the same
        mappings this resolver applies to tool queries, in a form that can be shown
        to the model (graph_in_context conditions with `graph_aliases: resolver`).
        Entries whose alias equals the displayed node name are dropped.
        """
        wanted = set(categories)
        table: Dict[str, str] = {}
        for alias, node in list(self.layer_aliases.items()) + list(self.extra_aliases.items()):
            cat = "layer_label" if alias in self.layer_aliases else ALIAS_CATEGORY.get(alias, "extra_alias")
            shown = self.display(node)
            if cat in wanted and alias != shown:
                table[alias] = shown
        return dict(sorted(table.items()))

    def resolve(self, descriptor) -> Optional[str]:
        """Return the canonical node name for `descriptor`, or None if not in the graph."""
        if not isinstance(descriptor, str) or not descriptor:
            return None
        if descriptor in self.nodes:
            return descriptor
        hit = self._index.get(normalize_label(descriptor))
        if hit is not None:
            return hit
        return self._compact_index.get(compact_label(descriptor))

    @classmethod
    def from_graph(cls, graph, extra_aliases: Optional[Dict[str, str]] = None,
                   display_corrections: Optional[Dict[str, str]] = None) -> "LabelResolver":
        """Build a resolver over all nodes of a CoffeeDescriptionGraph."""
        return cls(graph.descriptions, extra_aliases=extra_aliases, display_corrections=display_corrections)
