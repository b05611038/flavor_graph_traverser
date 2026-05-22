#!/usr/bin/env python3
"""
Inspect Questions for Quality Issues

Checks generated questions for:
1. Duplicate descriptors within a task type
2. Data leakage (components appearing in tool graph)
3. Category distribution balance

Usage:
    python scripts/inspect_questions.py                          # Inspect all task types
    python scripts/inspect_questions.py --task-type A3           # Inspect only A3
    python scripts/inspect_questions.py --confirmed-only         # Only confirmed questions
"""

import argparse
import json
import pickle
import sys
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def load_tool_graph_nodes(tool_graph_path: str) -> set:
    """Load all non-ROOT nodes from the tool graph."""
    path = Path(tool_graph_path)
    if not path.exists():
        print(f"  Warning: Tool graph not found at {tool_graph_path}")
        return set()

    with open(path, 'rb') as f:
        tool_data = pickle.load(f)

    nodes = set(tool_data['descriptions'])
    # Remove ROOT nodes
    nodes = {n for n in nodes if not n.startswith('ROOT:')}
    return nodes


def load_questions(questions_path: str, task_type_filter: str = None,
                   confirmed_only: bool = False, audit_state_path: str = None):
    """Load questions with optional filtering."""
    with open(questions_path) as f:
        data = json.load(f)
    questions = data['questions']

    # Filter by task type
    if task_type_filter:
        questions = [q for q in questions if q['task_type'].startswith(task_type_filter)
                     or q['id'].startswith(task_type_filter)]

    # Filter by confirmed status
    if confirmed_only and audit_state_path:
        state_path = Path(audit_state_path)
        if state_path.exists():
            with open(state_path) as f:
                states = json.load(f)
            questions = [q for q in questions if states.get(q['id'], {}).get('status') == 'confirmed']

    return questions


def check_duplicates(questions, task_type_label=""):
    """Check for duplicate descriptors within the question set."""
    # Group by task type
    by_type = defaultdict(list)
    for q in questions:
        by_type[q['task_type']].append(q)

    total_dupes = 0
    for task_type, type_questions in sorted(by_type.items()):
        descriptors = defaultdict(list)
        for q in type_questions:
            desc = q.get('_objects', {}).get('descriptor')
            if desc:
                descriptors[desc].append(q['id'])

        dupes = {k: v for k, v in descriptors.items() if len(v) > 1}
        if dupes:
            print(f"  [{task_type}] {len(dupes)} duplicate descriptors:")
            for desc, qids in dupes.items():
                print(f"    \"{desc}\" in {len(qids)} questions: {qids}")
                total_dupes += len(qids) - 1

    return total_dupes


def check_leakage(questions, tool_nodes, task_type_label=""):
    """Check for data leakage (components appearing in tool graph)."""
    from FlavorGraphTraverser.generation.validators import PROTECTED_FIELDS, PROTECTED_LIST_FIELDS

    total_leaks = 0
    leaked_questions = []

    for q in questions:
        objects = q.get('_objects', {})
        leaks = []

        # Check protected string fields
        for field in PROTECTED_FIELDS:
            value = objects.get(field)
            if isinstance(value, str) and value in tool_nodes:
                leaks.append(f"{field}: \"{value}\"")

        # Check protected list fields
        for field in PROTECTED_LIST_FIELDS:
            value = objects.get(field)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item in tool_nodes:
                        leaks.append(f"{field}[]: \"{item}\"")

        if leaks:
            leaked_questions.append((q['id'], leaks))
            total_leaks += len(leaks)

    if leaked_questions:
        # Group by task type
        by_type = defaultdict(list)
        for qid, leaks in leaked_questions:
            task_type = qid.split('_')[0] + '_' + '_'.join(qid.split('_')[1:-1])
            by_type[task_type].append((qid, leaks))

        for task_type, items in sorted(by_type.items()):
            print(f"  [{task_type}] {len(items)} questions with leakage:")
            for qid, leaks in items:
                for leak in leaks:
                    print(f"    {qid}: {leak}")

    return total_leaks


def check_distribution(questions, task_type_label=""):
    """Check category distribution of questions."""
    by_type = defaultdict(list)
    for q in questions:
        by_type[q['task_type']].append(q)

    for task_type, type_questions in sorted(by_type.items()):
        # Determine which field represents the category
        categories = []
        for q in type_questions:
            objects = q.get('_objects', {})
            # Use ancestor for A2, parent for A3, root category for A1
            if 'ancestor' in objects:
                categories.append(objects['ancestor'])
            elif 'parent' in objects:
                categories.append(objects['parent'])
            elif 'all_valid_roots' in objects:
                for root in objects['all_valid_roots']:
                    categories.append(root)
            else:
                categories.append('unknown')

        counts = Counter(categories)
        print(f"  [{task_type}] {len(type_questions)} questions, {len(counts)} categories:")
        for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")

        # Check Yes/No balance for A2
        if task_type.startswith('A2'):
            yes_count = sum(1 for q in type_questions if q.get('_objects', {}).get('is_ancestor'))
            no_count = len(type_questions) - yes_count
            print(f"    Yes/No: {yes_count}/{no_count} ({yes_count / len(type_questions) * 100:.0f}%/{no_count / len(type_questions) * 100:.0f}%)")


def main():
    parser = argparse.ArgumentParser(description="Inspect questions for quality issues")
    parser.add_argument(
        '--questions',
        default='data/questions/all_questions_system.json',
        help="Path to questions file"
    )
    parser.add_argument(
        '--tool-graph',
        default='data/graphs/coffee_flavor_wheel.json',
        help="Path to tool graph for leakage checking"
    )
    parser.add_argument(
        '--task-type',
        default=None,
        help="Filter by task type prefix (e.g., A3, E1)"
    )
    parser.add_argument(
        '--confirmed-only',
        action='store_true',
        help="Only inspect confirmed questions"
    )
    parser.add_argument(
        '--audit-state',
        default='data/audit_results/audit_state.json',
        help="Path to audit state file (for --confirmed-only)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Question Quality Inspection")
    print("=" * 70)
    print()

    # Load questions
    questions = load_questions(
        args.questions,
        task_type_filter=args.task_type,
        confirmed_only=args.confirmed_only,
        audit_state_path=args.audit_state
    )
    filter_desc = f" (task_type={args.task_type})" if args.task_type else ""
    filter_desc += " (confirmed only)" if args.confirmed_only else ""
    print(f"Loaded {len(questions)} questions{filter_desc}")
    print()

    # Load tool graph
    tool_nodes = load_tool_graph_nodes(args.tool_graph)
    print(f"Tool graph: {len(tool_nodes)} nodes (for leakage checking)")
    print()

    # 1. Check duplicates
    print("-" * 70)
    print("1. DUPLICATE CHECK")
    print("-" * 70)
    dup_count = check_duplicates(questions)
    if dup_count == 0:
        print("  ✓ No duplicate descriptors found")
    else:
        print(f"\n  ✗ Found {dup_count} duplicate(s)")
    print()

    # 2. Check leakage
    print("-" * 70)
    print("2. DATA LEAKAGE CHECK")
    print("-" * 70)
    leak_count = check_leakage(questions, tool_nodes)
    if leak_count == 0:
        print("  ✓ No data leakage found")
    else:
        print(f"\n  ✗ Found {leak_count} leaked component(s)")
    print()

    # 3. Check distribution
    print("-" * 70)
    print("3. CATEGORY DISTRIBUTION")
    print("-" * 70)
    check_distribution(questions)
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    issues = dup_count + leak_count
    if issues == 0:
        print(f"  ✓ All {len(questions)} questions pass quality checks")
    else:
        print(f"  ✗ {issues} issue(s) found in {len(questions)} questions")
        print(f"    - Duplicates: {dup_count}")
        print(f"    - Leakage: {leak_count}")
    print()

    return 1 if issues > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
