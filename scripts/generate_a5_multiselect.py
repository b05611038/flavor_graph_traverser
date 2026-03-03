#!/usr/bin/env python3
"""
Generate A5 multi-select questions: "Which are common ancestors of BOTH X and Y?"

Format:
- Multi-select: Select ALL correct common ancestors
- 5 options (A-E)
- Answer: List of letters (e.g., ['A', 'C'] or [] for NONE)

Valid options:
- Nodes that are ancestors of BOTH descriptors (common ancestors)
- Excludes ROOT:SYSTEM (structural node, not a flavor category)

Distractor strategy (plausible but wrong):
  Tier 0 - Hardest (parent of LCA — too general):
    e.g. LCA="berry fruit": add "fruity" as distractor (correct family, but too high)
  Tier 1 - Hard (ancestors of only ONE descriptor):
    e.g. pair=(strawberry, lemon): "berry fruit" is ancestor of strawberry only
  Tier 2 - Medium (children of the LCA — too specific):
    e.g. LCA="berry fruit": "red berry", "blue berry" look plausible but too low
  Tier 3 - Medium (siblings of the LCA — same level, wrong branch):
    e.g. LCA="berry fruit": "stone fruit", "citrus fruit" at same level but wrong branch
  Fallback - other nodes in same root category

Option A: LCA depth ≥ 1 required (LCA must NOT be a root category).
  Pairs that only share a root (e.g. "fruity") are rejected.
  Root category is added as a tier-0 "too general" distractor instead.

Option C: Distribution skewed toward 2 correct answers for added difficulty.
"""

import sys
import json
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph


def map_category_for_display(node):
    """Map internal category names to display names."""
    if node == 'defected':
        return 'other'
    return node


def is_leaf_node(graph, node):
    """Check if a node is a leaf (has no children)."""
    children = graph.get_children(node)
    return not children or len(children) == 0


def get_common_ancestors(graph, desc1, desc2):
    """Get all common ancestors of two descriptors, excluding ROOT:SYSTEM."""
    ancestors1 = set(graph.get_ancestors(desc1))
    ancestors2 = set(graph.get_ancestors(desc2))

    common = ancestors1 & ancestors2

    # Filter out ROOT:SYSTEM
    common = {a for a in common if a != 'ROOT:SYSTEM'}

    return common


_depth_cache = {}

def get_node_depth(graph, node):
    """Get the depth of a node in the hierarchy (distance from root)."""
    if node in _depth_cache:
        return _depth_cache[node]
    ancestors = graph.get_ancestors(node)
    ancestors = [a for a in ancestors if a != 'ROOT:SYSTEM']
    _depth_cache[node] = len(ancestors)
    return len(ancestors)


def get_lca(graph, common_ancestors):
    """Return the deepest common ancestor (lowest in tree = most specific)."""
    if not common_ancestors:
        return None
    return max(common_ancestors, key=lambda n: get_node_depth(graph, n))


def get_plausible_distractors(graph, desc1, desc2, common_ancestors, exclude_roots=None):
    """
    Build a tiered pool of plausible-but-wrong distractors.

    Tier 0 (hardest): parent of the LCA — correct family but too general
        e.g. LCA="berry fruit" → add "fruity" (looks right, but too high)
    Tier 1 (hard): ancestors of ONLY one descriptor
        e.g. "berry fruit" is ancestor of strawberry but not lemon
    Tier 2 (medium): children of the LCA — too specific
        e.g. LCA="berry fruit" → "red berry", "blue berry"
    Tier 3 (medium): siblings of the LCA — same level, wrong branch
        e.g. LCA="berry fruit" → "stone fruit", "citrus fruit"
    Fallback: other nodes in same root category

    Returns dict with tier keys.
    """
    if exclude_roots is None:
        exclude_roots = {'taste', 'baked', 'ROOT:SYSTEM'}

    ancestors1 = set(graph.get_ancestors(desc1))
    ancestors2 = set(graph.get_ancestors(desc2))
    common = set(common_ancestors)

    # Tier 1: ancestors of only one descriptor
    only1 = (ancestors1 - ancestors2 - common - {'ROOT:SYSTEM'})
    only2 = (ancestors2 - ancestors1 - common - {'ROOT:SYSTEM'})
    tier1 = list(only1 | only2)

    # Tier 2: children of common ancestors (too specific)
    tier2 = []
    for ca in common:
        for child in graph.get_children(ca):
            if (child not in common and child != desc1 and child != desc2
                    and not child.startswith('ROOT:')):
                tier2.append(child)

    # Tier 3: siblings of common ancestors (same level, different branch)
    tier3 = []
    for ca in common:
        parent = graph.get_parent(ca)
        if parent and parent != 'ROOT:SYSTEM':
            for sibling in graph.get_children(parent):
                if (sibling != ca and sibling not in common
                        and sibling not in exclude_roots
                        and not sibling.startswith('ROOT:')):
                    tier3.append(sibling)

    # Fallback: other nodes sharing the same root as either descriptor
    all_ancestors = ancestors1 | ancestors2
    root_cats = {a for a in all_ancestors
                 if graph.get_parent(a) in ('ROOT:SYSTEM', None)}

    fallback = []
    for node in graph.descriptions:
        if node.startswith('ROOT:'):
            continue
        if node in exclude_roots:
            continue
        if node in all_ancestors or node in common or node in {desc1, desc2}:
            continue
        node_ancestors = set(graph.get_ancestors(node))
        node_roots = {a for a in node_ancestors
                      if graph.get_parent(a) in ('ROOT:SYSTEM', None)}
        if node_roots & root_cats:
            fallback.append(node)

    return {
        'tier1': list(set(tier1)),
        'tier2': list(set(tier2)),
        'tier3': list(set(tier3)),
        'fallback': fallback,
    }


def get_valid_descriptors(graph, tool_leaf_nodes, exclude_roots=None):
    """Get all valid descriptors (not pairs, just individual nodes)."""
    if exclude_roots is None:
        exclude_roots = {'taste', 'baked'}

    valid_descriptors = []

    for node in graph.descriptions:
        if node.lower() in tool_leaf_nodes:
            continue
        if node.startswith('ROOT:'):
            continue

        # Get root category
        ancestors = graph.get_ancestors(node)
        if ancestors:
            path = list(reversed(ancestors))
            roots_in_path = [n for n in path if n != 'ROOT:SYSTEM']

            if roots_in_path and roots_in_path[0] not in exclude_roots:
                valid_descriptors.append(node)

    return valid_descriptors


def build_deep_pair_index(graph, valid_descriptors):
    """
    Pre-compute pairs that share at least one common ancestor at depth >= 1.
    Groups descriptors by their non-root ancestors so we can sample nearby pairs.

    Returns: dict mapping intermediate_node -> [descriptors that have it as ancestor]
    """
    node_to_descs = {}
    for desc in valid_descriptors:
        ancestors = graph.get_ancestors(desc)
        for anc in ancestors:
            if anc == 'ROOT:SYSTEM':
                continue
            depth = get_node_depth(graph, anc)
            if depth >= 1:  # not a root category
                if anc not in node_to_descs:
                    node_to_descs[anc] = []
                node_to_descs[anc].append(desc)

    # Keep only nodes with 2+ descriptors (so we can form pairs)
    return {n: descs for n, descs in node_to_descs.items() if len(descs) >= 2}


def sample_deep_pair(deep_pair_index, graph):
    """
    Sample a pair guaranteed to share a common ancestor at depth >= 1.
    Picks a random intermediate node, then picks two of its descendants.
    """
    if not deep_pair_index:
        return None, None, set()

    # Pick a random intermediate node
    node = random.choice(list(deep_pair_index.keys()))
    descs = deep_pair_index[node]

    if len(descs) < 2:
        return None, None, set()

    desc1, desc2 = random.sample(descs, 2)
    common = get_common_ancestors(graph, desc1, desc2)
    return desc1, desc2, common


def sample_distractors(distractor_pools, n, exclude):
    """
    Sample n distractors from tiered pools, prioritising harder tiers.

    Draw from tier1 first, then tier2, tier3, fallback until we have n.
    """
    selected = []
    seen = set(exclude)

    for tier in ('tier1', 'tier2', 'tier3', 'fallback'):
        pool = [x for x in distractor_pools[tier] if x not in seen]
        random.shuffle(pool)
        for candidate in pool:
            if len(selected) >= n:
                break
            selected.append(candidate)
            seen.add(candidate)
        if len(selected) >= n:
            break

    return selected


def generate_multiselect_question(desc1, desc2, common_ancestors, graph, used_descriptors_global, used_pairs_global):
    """
    Generate one multi-select A5 question with plausible distractors.

    Option A: Requires LCA depth >= 1 (not a root category).
      Root categories (depth 0) are used as tier-0 distractors instead.

    Option C: Distribution skewed toward 2 correct answers.
    - 0 valid: 5%
    - 1 valid: 25%
    - 2 valid: 40%  ← peak (up from 30%)
    - 3 valid: 20%
    - 4 valid: 7%
    - 5 valid: 3%
    """
    pair_key = tuple(sorted([desc1, desc2]))
    if pair_key in used_pairs_global:
        return None, set()
    if desc1 in used_descriptors_global or desc2 in used_descriptors_global:
        return None, set()

    # Option A: require at least one common ancestor at depth >= 1
    # (pair selection filter only — ALL common ancestors are valid answers)
    deep_common = {a for a in common_ancestors if get_node_depth(graph, a) >= 1}
    if not deep_common:
        return None, set()  # Only shared root — reject this pair

    # Option C: distribution skewed toward 2 correct answers
    distribution = [0]*5 + [1]*25 + [2]*40 + [3]*20 + [4]*7 + [5]*3
    num_valid = random.choice(distribution)
    # Valid pool = ALL common ancestors (root + intermediate), not just deep ones
    num_valid = min(num_valid, len(common_ancestors))
    num_invalid = 5 - num_valid

    # Select valid options (common ancestors)
    valid_options = random.sample(list(common_ancestors), num_valid) if num_valid > 0 else []

    # Build tiered distractor pool
    distractor_pools = get_plausible_distractors(
        graph, desc1, desc2, common_ancestors
    )

    # Require that tier1+tier2+tier3+fallback is large enough
    total_available = sum(len(v) for v in distractor_pools.values())
    if total_available < num_invalid:
        return None, set()

    invalid_options = sample_distractors(
        distractor_pools, num_invalid, exclude=set(valid_options) | {desc1, desc2}
    )

    if len(invalid_options) < num_invalid:
        return None, set()

    # Combine and shuffle
    all_options = []
    correct_letters = []

    for node in valid_options:
        all_options.append(('VALID', node))

    for node in invalid_options:
        all_options.append(('INVALID', node))

    random.shuffle(all_options)

    # Build question with 5 options (A-E)
    letters = ['A', 'B', 'C', 'D', 'E']
    options = {}

    for i, (status, node) in enumerate(all_options):
        letter = letters[i]
        options[letter] = map_category_for_display(node)

        if status == 'VALID':
            correct_letters.append(letter)

    # Sort correct answers for consistency
    correct_letters.sort()

    # Format question text with conditional footnote for 'other'
    desc1_display = map_category_for_display(desc1)
    desc2_display = map_category_for_display(desc2)

    question_text = f"Which of the following are common ancestors of BOTH '{desc1_display}' and '{desc2_display}'? (Select all that apply, or none if there are no common ancestors)"

    # Check if any option contains 'other'
    has_other = any(opt == 'other' for opt in options.values())
    if has_other:
        question_text += "\n\n*'other' includes non-standard or less common flavor categories"

    question = {
        'id': f"A5_multiselect_{random.randint(10000000, 99999999):08x}",
        'category': 'A',
        'task_type': 'A5_lca_finding_multiselect',
        'text': question_text,
        'options': options,
        'correct_answer': correct_letters,  # List of letters
        '_template': "Which of the following are common ancestors of BOTH '{descriptor1}' and '{descriptor2}'?",
        '_objects': {
            'descriptor1': desc1,
            'descriptor2': desc2,
            'common_ancestors': list(common_ancestors),
            'num_valid': num_valid,
            'num_invalid': num_invalid,
            'valid_options': valid_options,
            'invalid_options': invalid_options,
            'lca': get_lca(graph, common_ancestors)
        }
    }

    return question, {desc1, desc2}


def main():
    random.seed(42)

    print("Generating A5 multi-select questions (LCA finding)")
    print("=" * 70)

    # Load graphs
    system_data = load_graph_data("data/graphs/system_graph.pkl")
    system_graph = CoffeeDescriptionGraph(
        system_data['descriptions'],
        system_data['connections'],
        root=system_data['root']
    )

    tool_data = load_graph_data("data/graphs/coffee_flavor_wheel.pkl")
    tool_nodes = {n.lower() for n in tool_data['descriptions'] if not n.startswith('ROOT:')}

    tool_graph = CoffeeDescriptionGraph(
        tool_data['descriptions'],
        tool_data['connections'],
        tool_data['root']
    )
    tool_leaf_nodes = {n.lower() for n in tool_data['descriptions']
                       if is_leaf_node(tool_graph, n) and not n.startswith('ROOT:')}

    print(f"System graph: {len(system_graph.descriptions)} nodes")
    print(f"Tool exclusions: {len(tool_nodes)} nodes")
    print()

    # Get all valid descriptors and build deep-pair index
    valid_descriptors = get_valid_descriptors(system_graph, tool_leaf_nodes)
    print(f"Found {len(valid_descriptors)} valid descriptors")

    print("Building deep-pair index (depth >= 1 common ancestors)...")
    deep_pair_index = build_deep_pair_index(system_graph, valid_descriptors)
    print(f"Intermediate nodes with 2+ descendants: {len(deep_pair_index)}")
    print()

    # Target: 80 questions (to select best ~11 at ~15% acceptance rate)
    TARGET_COUNT = 80

    # Load existing questions to prevent duplicate descriptor pairs
    used_descriptors_global = set()
    used_pairs_global = set()
    master_file = Path("data/questions/all_questions_system.json")
    if master_file.exists():
        with open(master_file) as f:
            existing = json.load(f)
        for q in existing.get('questions', []):
            if q.get('task_type', '').startswith('A5_lca_finding'):
                obj = q.get('_objects', {})
                d1 = obj.get('descriptor1', '')
                d2 = obj.get('descriptor2', '')
                if d1 and d2:
                    used_pairs_global.add(tuple(sorted([d1, d2])))
        print(f"Excluding {len(used_pairs_global)} existing A5 descriptor pairs")
        print()

    generated = []
    attempts = 0
    max_attempts = 5000

    while len(generated) < TARGET_COUNT and attempts < max_attempts:
        attempts += 1

        # Sample a pair guaranteed to share depth >= 1 ancestor
        desc1, desc2, common = sample_deep_pair(deep_pair_index, system_graph)

        if not desc1 or not desc2:
            continue

        question, used_local = generate_multiselect_question(
            desc1, desc2, common, system_graph, used_descriptors_global, used_pairs_global
        )

        if question:
            generated.append(question)
            used_descriptors_global.update(used_local)
            used_pairs_global.add(tuple(sorted([desc1, desc2])))

            num_valid = question['_objects']['num_valid']
            num_invalid = question['_objects']['num_invalid']
            correct = question['correct_answer']

            print(f"{len(generated):3}. {desc1[:20]:20} + {desc2[:20]:20} | Valid={num_valid}, Invalid={num_invalid}, Correct={correct}")

    print()
    print(f"Generated {len(generated)}/{TARGET_COUNT} questions from {attempts} attempts")
    print()

    # Show distributions
    valid_dist = {}
    for q in generated:
        num_valid = q['_objects']['num_valid']
        valid_dist[num_valid] = valid_dist.get(num_valid, 0) + 1

    print("Valid options distribution:")
    for num in sorted(valid_dist.keys()):
        pct = valid_dist[num] / len(generated) * 100
        print(f"  {num} valid: {valid_dist[num]:2} questions ({pct:5.1f}%)")
    print()

    # Save to file
    output_file = "data/questions/a5_multiselect_questions.json"

    output_data = {
        'metadata': {
            'total_questions': len(generated),
            'task_type': 'A5_lca_finding_multiselect',
            'generation_method': 'multiselect_common_ancestors',
            'question_format': 'Which are common ancestors of BOTH X and Y?',
            'answer_format': 'list_of_letters',
            'constraints': [
                'Multi-select: 0-5 correct answers per question',
                'Valid options: Common ancestors of both descriptors',
                'Invalid options: Ancestors of only one, or unrelated nodes',
                'Blocks ROOT:SYSTEM from appearing in options',
                'Display mapping: defected → other'
            ]
        },
        'questions': generated
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Saved {len(generated)} questions to {output_file}")
    print()

    # Show samples
    if generated:
        print("Sample questions:")
        print()

        for i, q in enumerate(generated[:3], 1):
            print(f"Question {i}:")
            print(f"  {q['text']}")
            print()

            for letter in sorted(q['options'].keys()):
                marker = '✓' if letter in q['correct_answer'] else ' '
                print(f"    {letter}. {q['options'][letter]} {marker}")

            print(f"  Correct answers: {', '.join(q['correct_answer']) if q['correct_answer'] else 'NONE'}")
            print(f"  ({q['_objects']['num_valid']} valid, {q['_objects']['num_invalid']} invalid)")
            print(f"  LCA: {map_category_for_display(q['_objects']['lca']) if q['_objects']['lca'] else 'N/A'}")
            print()


if __name__ == "__main__":
    main()
