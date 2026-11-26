"""
Tests for LabelResolver, the resolver-backed executor, build_executor and the graph renderer
(tool_resolved and graph_in_context conditions).
"""

import pytest

from FlavorGraphTraverser.evaluation.tools import (
    GraphToolExecutor,
    LabelResolver,
    build_executor,
    normalize_label,
    render_graph,
)


@pytest.fixture(scope="module")
def exact(coffee_flavor_wheel_graph):
    return build_executor(coffee_flavor_wheel_graph, {})


@pytest.fixture(scope="module")
def resolved(coffee_flavor_wheel_graph):
    return build_executor(coffee_flavor_wheel_graph, {"label_resolution": "resolve"})


class TestLabelResolver:
    def test_layer_aliases_point_to_inner_ring(self, coffee_flavor_wheel_graph):
        r = LabelResolver.from_graph(coffee_flavor_wheel_graph)
        assert r.layer_aliases == {
            "floral": "floral (inner layer)",
            "green/vegetative": "green/vegetative (inner layer)",
        }

    def test_benchmark_spelling_alias(self, coffee_flavor_wheel_graph):
        r = LabelResolver.from_graph(coffee_flavor_wheel_graph)
        assert r.resolve("green/vegetable") == "green/vegetative (inner layer)"

    @pytest.mark.parametrize("query,expected", [
        ("Floral", "floral (inner layer)"),
        ("  FLORAL ", "floral (inner layer)"),
        ("Green/Vegetative", "green/vegetative (inner layer)"),
        ("black tea", "black_tea"),
        ("Black  Tea", "black_tea"),
        ("Rose", "rose"),
    ])
    def test_surface_variants(self, coffee_flavor_wheel_graph, query, expected):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).resolve(query) == expected

    @pytest.mark.parametrize("query", ["green", "blueberry jam", "", None, 3, ["rose"]])
    def test_unresolvable(self, coffee_flavor_wheel_graph, query):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).resolve(query) is None

    def test_every_node_resolves_to_itself(self, coffee_flavor_wheel_graph):
        r = LabelResolver.from_graph(coffee_flavor_wheel_graph)
        for node in coffee_flavor_wheel_graph.descriptions:
            assert r.resolve(node) == node

    def test_qualified_names_still_exact(self, coffee_flavor_wheel_graph):
        r = LabelResolver.from_graph(coffee_flavor_wheel_graph)
        assert r.resolve("floral (middle layer)") == "floral (middle layer)"

    def test_ambiguous_alias_rejected(self):
        with pytest.raises(ValueError, match="Ambiguous"):
            LabelResolver(["black_tea", "black tea"])

    def test_extra_alias_with_missing_target_ignored(self):
        r = LabelResolver(["rose"], extra_aliases={"roses": "rose", "x": "not-a-node"})
        assert r.resolve("roses") == "rose"
        assert r.resolve("x") is None

    def test_normalize_label(self):
        assert normalize_label("  Black_Tea ") == "black tea"


class TestResolvedExecutor:
    def test_validate_reports_resolution(self, resolved):
        out = resolved.validate_descriptors(["floral", "rose", "blueberry jam"])
        assert out == {
            "valid": ["floral", "rose"],
            "invalid": ["blueberry jam"],
            "resolved": {"floral": "floral (inner layer)"},
        }

    def test_get_children_on_bare_label(self, resolved):
        out = resolved.get_children("floral")
        assert out["error"] is None
        assert out["resolved_to"] == "floral (inner layer)"
        assert set(out["children"]) == {"floral (middle layer)", "black tea"}

    def test_get_parent_on_benchmark_spelling(self, resolved):
        out = resolved.get_parent("green/vegetable")
        assert out["resolved_to"] == "green/vegetative (inner layer)"
        assert out["parents"] == ["ROOT:coffee_flavor_wheel"]

    def test_exact_hit_has_no_resolution_field(self, resolved):
        assert "resolved_to" not in resolved.get_parent("jasmine")
        assert "resolved" not in resolved.validate_descriptors(["jasmine"])

    def test_not_found_message_unchanged(self, exact, resolved):
        assert resolved.get_parent("blueberry jam") == exact.get_parent("blueberry jam")

    def test_is_valid_descriptor(self, exact, resolved):
        assert resolved.is_valid_descriptor("floral")
        assert not exact.is_valid_descriptor("floral")


class TestExactModeUnchanged:
    """build_executor default must reproduce the original experiment's tool outputs."""

    QUERIES = ["floral", "Floral", "green/vegetable", "black tea", "black_tea", "rose",
               "floral (inner layer)", "jasmine", "fruity", "blueberry jam", ""]

    def test_default_mode_is_exact(self, coffee_flavor_wheel_graph):
        assert build_executor(coffee_flavor_wheel_graph, {}).resolver is None
        assert build_executor(coffee_flavor_wheel_graph, {"label_resolution": "exact"}).resolver is None

    def test_unknown_mode_rejected(self, coffee_flavor_wheel_graph):
        with pytest.raises(ValueError):
            build_executor(coffee_flavor_wheel_graph, {"label_resolution": "fuzzy"})

    def test_bare_labels_invalid_in_exact_mode(self, exact):
        assert exact.validate_descriptors(["floral", "green/vegetable", "black tea"]) == {
            "valid": [], "invalid": ["floral", "green/vegetable", "black tea"]}

    @pytest.mark.parametrize("q", QUERIES)
    def test_matches_plain_executor(self, coffee_flavor_wheel_graph, exact, q):
        plain = GraphToolExecutor(coffee_flavor_wheel_graph)
        assert exact.get_parent(q) == plain.get_parent(q)
        assert exact.get_children(q) == plain.get_children(q)
        assert exact.validate_descriptors([q]) == plain.validate_descriptors([q])

    def test_resolved_equals_exact_on_exact_hits(self, exact, resolved, coffee_flavor_wheel_graph):
        """For any query that already matched, resolution changes nothing except the
        display of misspelled / underscored node names."""
        fix = resolved.resolver.display
        for node in coffee_flavor_wheel_graph.descriptions:
            for method, key in ((exact.get_parent, "parents"), (exact.get_children, "children")):
                expected = dict(method(node))
                expected[key] = [fix(n) for n in expected[key]]
                got = dict(getattr(resolved, method.__name__)(node))
                if fix(node) != node:
                    assert got.pop("resolved_to") == fix(node)
                assert got == expected


class TestGraphRender:
    def test_tree_contains_every_non_root_node_once(self, coffee_flavor_wheel_graph):
        lines = render_graph(coffee_flavor_wheel_graph, "tree").splitlines()
        names = [l.strip() for l in lines]
        expected = [n for n in coffee_flavor_wheel_graph.descriptions if n != coffee_flavor_wheel_graph.root]
        assert sorted(names) == sorted(expected)

    def test_tree_indentation_reflects_parent(self, coffee_flavor_wheel_graph):
        lines = render_graph(coffee_flavor_wheel_graph, "tree").splitlines()
        i = lines.index("floral (inner layer)")
        assert "  floral (middle layer)" in lines[i + 1:i + 3]
        assert "    jasmine" in lines

    def test_edges_format(self, coffee_flavor_wheel_graph):
        edges = render_graph(coffee_flavor_wheel_graph, "edges").splitlines()
        assert "(floral (middle layer), jasmine)" in edges
        assert not any(" > " in e for e in edges)
        assert not any(e.startswith("ROOT:") for e in edges)

    def test_json_nesting_and_leaves(self, coffee_flavor_wheel_graph):
        import json
        text = render_graph(coffee_flavor_wheel_graph, "json")
        obj = json.loads(text)
        assert len(obj) == 9
        assert obj["floral (inner layer)"]["floral (middle layer)"]["jasmine"] == {}

        def keys(d):
            for k, v in d.items():
                yield k
                yield from keys(v)
        expected = [n for n in coffee_flavor_wheel_graph.descriptions if n != coffee_flavor_wheel_graph.root]
        assert sorted(keys(obj)) == sorted(expected)
        assert " > " not in text

    def test_json_parents_with_mixed_children_use_one_leaf_rule(self, coffee_flavor_wheel_graph):
        import json
        obj = json.loads(render_graph(coffee_flavor_wheel_graph, "json"))

        def values(d):
            for v in d.values():
                assert isinstance(v, dict)
                yield from values(v)
        list(values(obj))

    def test_unknown_format(self, coffee_flavor_wheel_graph):
        with pytest.raises(ValueError):
            render_graph(coffee_flavor_wheel_graph, "yaml")


class TestToolGraphDefects:
    """Misspelled / underscored node names in the tool-graph file."""

    @pytest.mark.parametrize("query,node", [
        ("grapefruit", "graphfruit"), ("Grapefruit", "graphfruit"), ("graphfruit", "graphfruit"),
        ("maple syrup", "mapple syrup"), ("mapple syrup", "mapple syrup"),
        ("green vegetative", "green/vegetative (inner layer)"),
        ("green/vegetal", "green/vegetative (inner layer)"),
        ("green/ vegetative", "green/vegetative (inner layer)"),
    ])
    def test_resolves(self, coffee_flavor_wheel_graph, query, node):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).resolve(query) == node

    @pytest.mark.parametrize("query", ["floral (outer layer)", "floral (top layer)", "roast", "pea"])
    def test_deliberately_unresolved(self, coffee_flavor_wheel_graph, query):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).resolve(query) is None

    def test_outputs_show_corrected_spelling(self, resolved):
        out = resolved.get_children("citrus fruit")
        assert "grapefruit" in out["children"] and "graphfruit" not in out["children"]
        assert "resolved_to" not in out

    def test_exact_mode_keeps_stored_spelling(self, exact):
        assert "graphfruit" in exact.get_children("citrus fruit")["children"]
        assert exact.validate_descriptors(["grapefruit"])["invalid"] == ["grapefruit"]

    def test_corrected_query_needs_no_resolution_note(self, resolved):
        assert resolved.validate_descriptors(["grapefruit"]) == {"valid": ["grapefruit"], "invalid": []}
        assert resolved.validate_descriptors(["graphfruit"])["resolved"] == {"graphfruit": "grapefruit"}

    @pytest.mark.parametrize("query,category", [
        ("floral", "layer_label"), ("green/ vegetative", "layer_label"),
        ("green vegetative", "layer_label_variant"), ("green/vegetable", "benchmark_spelling"),
        ("grapefruit", "tool_graph_misspelling"), ("black tea", "surface_normalization"),
        ("Fruity", "surface_normalization"), ("rose", None), ("blueberry jam", None),
    ])
    def test_classify(self, coffee_flavor_wheel_graph, query, category):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).classify(query) == category

    def test_graph_render_name_map(self, coffee_flavor_wheel_graph):
        from FlavorGraphTraverser.evaluation.tools import DEFAULT_DISPLAY_CORRECTIONS
        for fmt in ("json", "tree"):
            raw = render_graph(coffee_flavor_wheel_graph, fmt)
            fixed = render_graph(coffee_flavor_wheel_graph, fmt, name_map=DEFAULT_DISPLAY_CORRECTIONS)
            assert "graphfruit" in raw and "graphfruit" not in fixed and "grapefruit" in fixed
        raw = render_graph(coffee_flavor_wheel_graph, "tree")
        fixed = render_graph(coffee_flavor_wheel_graph, "tree", name_map=DEFAULT_DISPLAY_CORRECTIONS)
        assert "graphfruit" in raw and "graphfruit" not in fixed and "grapefruit" in fixed
        assert "floral (inner layer)" in fixed


class TestAliasTable:
    def test_question_vocabulary_aliases(self, coffee_flavor_wheel_graph):
        table = LabelResolver.from_graph(coffee_flavor_wheel_graph).alias_table()
        assert table == {
            "floral": "floral (inner layer)",
            "green/vegetable": "green/vegetative (inner layer)",
            "green/vegetative": "green/vegetative (inner layer)",
            "whisky": "whiskey",
        }

    def test_every_alias_resolves_to_its_entry(self, coffee_flavor_wheel_graph):
        r = LabelResolver.from_graph(coffee_flavor_wheel_graph)
        for alias, shown in r.alias_table(categories=("layer_label", "benchmark_spelling",
                                                      "layer_label_variant", "tool_graph_misspelling")).items():
            assert r.display(r.resolve(alias)) == shown

    def test_misspellings_dropped_once_corrected(self, coffee_flavor_wheel_graph):
        table = LabelResolver.from_graph(coffee_flavor_wheel_graph).alias_table(
            categories=("tool_graph_misspelling",))
        assert table == {}


class TestRenderingAgainstRawFile:
    def test_json_parent_of_every_node_matches_file(self, coffee_flavor_wheel_graph):
        import json
        obj = json.loads(render_graph(coffee_flavor_wheel_graph, "json"))
        root = coffee_flavor_wheel_graph.root
        seen = {}

        def walk(d, parent):
            for k, v in d.items():
                assert k not in seen, f"{k} rendered twice"
                seen[k] = parent
                walk(v, k)
        walk(obj, root)
        for node, parent in seen.items():
            assert list(coffee_flavor_wheel_graph.parents_of_description(node)) == [parent]
        assert len(seen) == len(coffee_flavor_wheel_graph.descriptions) - 1

    def test_tree_parent_of_every_node_matches_file(self, coffee_flavor_wheel_graph):
        root = coffee_flavor_wheel_graph.root
        stack = []
        for line in render_graph(coffee_flavor_wheel_graph, "tree").splitlines():
            depth = (len(line) - len(line.lstrip(" "))) // 2
            name = line.strip()
            stack = stack[:depth] + [name]
            parent = stack[-2] if depth else root
            assert list(coffee_flavor_wheel_graph.parents_of_description(name)) == [parent]

    def test_duplicate_labels_placed_correctly(self, coffee_flavor_wheel_graph):
        import json
        obj = json.loads(render_graph(coffee_flavor_wheel_graph, "json"))
        assert set(obj["floral (inner layer)"]) == {"floral (middle layer)", "black_tea"}
        assert set(obj["floral (inner layer)"]["floral (middle layer)"]) == {"chamomile", "jasmine", "rose"}
        g = obj["green/vegetative (inner layer)"]
        assert set(g) == {"olive oil", "raw", "beany", "green/vegetative (middle layer)"}
        assert len(g["green/vegetative (middle layer)"]) == 7

    def test_non_tree_rejected(self):
        from FlavorGraphTraverser import CoffeeDescriptionGraph
        conns = [{"source": s, "target": t, "path_type": "x"} for s, t in [("R", "a"), ("R", "b"), ("a", "c"), ("b", "c")]]
        g = CoffeeDescriptionGraph(["R", "a", "b", "c"], conns, root="R")
        for fmt in ("json", "tree"):
            with pytest.raises(ValueError, match="twice"):
                render_graph(g, fmt)


class TestResolvedReachability:
    def test_every_node_reachable_by_displayed_names(self, coffee_flavor_wheel_graph, resolved):
        r = resolved.resolver
        start = [r.display(n) for n in coffee_flavor_wheel_graph.children_of_description(coffee_flavor_wheel_graph.root)]
        seen, queue = set(), list(start)
        while queue:
            name = queue.pop(0)
            node = r.resolve(name)
            assert node is not None and r.display(node) == name, name
            if node in seen:
                continue
            seen.add(node)
            queue.extend(resolved.get_children(name)["children"])
        assert seen == set(coffee_flavor_wheel_graph.descriptions) - {coffee_flavor_wheel_graph.root}

    def test_displayed_parent_names_round_trip(self, coffee_flavor_wheel_graph, resolved):
        r = resolved.resolver
        for node in coffee_flavor_wheel_graph.descriptions:
            if node == coffee_flavor_wheel_graph.root:
                continue
            parents = resolved.get_parent(r.display(node))["parents"]
            assert parents, node
            for p in parents:
                assert r.resolve(p) is not None, (node, p)


class TestSeparatorAndSpellingVariants:
    @pytest.mark.parametrize("query,node", [
        ("blacktea", "black_tea"), ("black-tea", "black_tea"), ("Black_Tea", "black_tea"),
        ("hay like", "hay-like"), ("haylike", "hay-like"),
        ("musty earthy", "musty/earthy"), ("green vegetable", "green/vegetative (inner layer)"),
        ("floral(inner layer)", "floral (inner layer)"), ("floral middle layer", "floral (middle layer)"),
        ("floral (middle)", "floral (middle layer)"),
        ("smokey", "smoky"), ("winy", "winey"), ("animallic", "animalic"),
    ])
    def test_resolves(self, coffee_flavor_wheel_graph, query, node):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).resolve(query) == node

    @pytest.mark.parametrize("query", [
        "}nutty", ":lemon",                      # malformed calls: other punctuation is significant
        "roast", "green", "greens",              # ambiguous
        "pea", "peas", "acid", "brown rice",     # near-misses of different words
        "blueberry jam",                         # compound phrases stay unresolved
    ])
    def test_still_unresolved(self, coffee_flavor_wheel_graph, query):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).resolve(query) is None

    def test_no_ambiguous_compact_keys(self, coffee_flavor_wheel_graph):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).ambiguous_compact_keys == []

    def test_ambiguous_compact_key_is_not_guessed(self):
        r = LabelResolver(["ab c", "a bc"])
        assert r.resolve("abc") is None and "abc" in r.ambiguous_compact_keys


class TestWordForms:
    @pytest.mark.parametrize("query,node", [
        ("fruit", "fruity"), ("Fruits", "fruity"), ("wine", "winey"), ("wood", "woody"),
        ("nuts", "nutty"), ("spice", "spices"), ("peanut", "peanuts"), ("raisins", "raisin"),
        ("brown spices", "brown spice"), ("sweet aromatic", "sweet aromatics"),
        ("sweetness", "sweet"), ("smoke", "smoky"), ("animal", "animalic"),
    ])
    def test_resolves(self, coffee_flavor_wheel_graph, query, node):
        r = LabelResolver.from_graph(coffee_flavor_wheel_graph)
        assert r.resolve(query) == node and r.classify(query) == "word_form"

    def test_word_forms_never_override_a_node(self, coffee_flavor_wheel_graph):
        r = LabelResolver.from_graph(coffee_flavor_wheel_graph)
        for node in coffee_flavor_wheel_graph.descriptions:
            assert r.resolve(node) == node

    def test_word_forms_not_in_prompt_alias_list(self, coffee_flavor_wheel_graph):
        assert "fruit" not in LabelResolver.from_graph(coffee_flavor_wheel_graph).alias_table()

    def test_word_forms_can_be_switched_off(self, coffee_flavor_wheel_graph):
        r = LabelResolver(coffee_flavor_wheel_graph.descriptions, word_forms={})
        assert r.resolve("fruit") is None


# (index keys, plural forms, extra aliases incl. word forms) — see test_index_size_snapshot
INDEX_SNAPSHOT = (305, 148, 32)


class TestPluralRule:
    @pytest.mark.parametrize("query,node", [
        ("berries", "berry"), ("strawberries", "strawberry"), ("cherries", "cherry"),
        ("whiskies", "whiskey"), ("peaches", "peach"), ("spice", "spices"),
    ])
    def test_number_forms(self, coffee_flavor_wheel_graph, query, node):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).resolve(query) == node

    def test_no_ambiguous_plural_forms(self, coffee_flavor_wheel_graph):
        assert LabelResolver.from_graph(coffee_flavor_wheel_graph).ambiguous_plural_forms == []

    def test_shared_plural_is_dropped_not_guessed(self):
        r = LabelResolver(["fish", "fishe"], word_forms={}, extra_aliases={})
        # "fishes" would be the plural of both "fish" and "fishe": dropped
        assert r.resolve("fishes") is None and "fishes" in r.ambiguous_plural_forms

    def test_index_size_snapshot(self, coffee_flavor_wheel_graph):
        """Any change to the resolver's mappings must be deliberate: update this snapshot
        (and re-run select_rerun_pairs.py) when the rules change."""
        r = LabelResolver.from_graph(coffee_flavor_wheel_graph)
        assert (len(r._index), len(r.plural_aliases), len(r.extra_aliases)) == INDEX_SNAPSHOT
