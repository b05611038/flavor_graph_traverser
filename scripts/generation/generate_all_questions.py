#!/usr/bin/env python3
"""
Generate Questions

Generates benchmark questions from the System Graph.
Supports generating all task types or specific ones.

Usage:
    python scripts/generate_all_questions.py              # Generate all task types
    python scripts/generate_all_questions.py E2            # Generate only E2
    python scripts/generate_all_questions.py E2 E3         # Generate E2 and E3
    python scripts/generate_all_questions.py A1 --count 200  # Generate A1 with custom count
    python scripts/generate_all_questions.py E2 --seed 999   # Use different random seed
"""

import sys
import json
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.generation import QuestionGenerator
from FlavorGraphTraverser.backup import backup_before_write

# Map short names to full task type names
TASK_TYPE_MAP = {
    'A1': 'A1_root_classification',
    'A2': 'A2_ancestor_verification',
    'A3': 'A3_sibling_identification',
    'A4': 'A4_path_reconstruction',
    'A5': 'A5_lca_finding',
    'E1': 'E1_similarity_ranking',
    'E2': 'E2_pairwise_comparison',
    'E3': 'E3_odd_one_out',
    'F':  'F_flavor_description',
}

# Map full task type to config section and key
TASK_CONFIG_SECTION = {
    'A1_root_classification': ('taxonomic', 'A1_root_classification'),
    'A2_ancestor_verification': ('taxonomic', 'A2_ancestor_verification'),
    'A3_sibling_identification': ('taxonomic', 'A3_sibling_identification'),
    'A4_path_reconstruction': ('taxonomic', 'A4_path_reconstruction'),
    'A5_lca_finding': ('taxonomic', 'A5_lca_finding'),
    'E1_similarity_ranking': ('similarity', 'E1_similarity_ranking'),
    'E2_pairwise_comparison': ('similarity', 'E2_pairwise_comparison'),
    'E3_odd_one_out': ('similarity', 'E3_odd_one_out'),
    'F_flavor_description': ('open_ended', 'F_flavor_description'),
}


def build_exclusion_set(system_graph, tool_data):
    """Build the full exclusion set from tool graph + non-flavor categories."""
    all_tool_nodes = set(tool_data['descriptions'])
    tool_nodes = {n for n in all_tool_nodes if not n.startswith('ROOT:')}

    non_flavor = set()

    # Exclude 'taste' and all descendants
    if 'taste' in system_graph.descriptions:
        queue = ['taste']
        visited = set(['taste'])
        while queue:
            node = queue.pop(0)
            for child in system_graph.get_children(node):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)
        non_flavor.update(visited)

    # Exclude structural/empty categories
    for n in ['baked', 'defected', 'ROOT:SYSTEM']:
        if n in system_graph.descriptions:
            non_flavor.add(n)

    exclude_set = tool_nodes | non_flavor
    return exclude_set, tool_nodes


def parse_args():
    parser = argparse.ArgumentParser(
        description='Generate benchmark questions from the System Graph.',
        epilog='Examples:\n'
               '  %(prog)s                  # Generate all task types\n'
               '  %(prog)s E2               # Generate only E2\n'
               '  %(prog)s E2 E3 --count 500  # E2 and E3, 500 attempts each\n'
               '  %(prog)s A1 --seed 999    # A1 with different seed\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'task_types', nargs='*',
        help=f'Task types to generate (default: all). Valid: {", ".join(sorted(TASK_TYPE_MAP.keys()))}',
    )
    parser.add_argument(
        '--count', type=int, default=None,
        help='Override the generation count (number of attempts)',
    )
    parser.add_argument(
        '--seed', type=int, default=None,
        help='Random seed (default: from config or 42)',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Resolve task types
    if args.task_types:
        task_types = []
        for t in args.task_types:
            t_upper = t.upper()
            if t_upper in TASK_TYPE_MAP:
                task_types.append(TASK_TYPE_MAP[t_upper])
            elif t in TASK_TYPE_MAP.values():
                task_types.append(t)
            else:
                print(f"Unknown task type: {t}")
                print(f"Valid: {', '.join(sorted(TASK_TYPE_MAP.keys()))}")
                return 1
        generating_all = False
    else:
        task_types = list(TASK_TYPE_MAP.values())
        generating_all = True

    # Load graphs
    system_graph_file = "data/graphs/system_graph.pkl"
    tool_graph_file = "data/graphs/coffee_flavor_wheel.pkl"

    if not Path(system_graph_file).exists():
        print(f"Graph file not found: {system_graph_file}")
        print("Please run: python scripts/dump_graphs.py")
        return 1

    system_data = load_graph_data(system_graph_file)
    system_graph = CoffeeDescriptionGraph(
        system_data['descriptions'], system_data['connections'], root=system_data['root']
    )
    print(f"System graph: {len(system_graph.descriptions)} nodes")

    if not Path(tool_graph_file).exists():
        print(f"Tool graph not found: {tool_graph_file}")
        return 1

    tool_data = load_graph_data(tool_graph_file)
    exclude_set, tool_nodes = build_exclusion_set(system_graph, tool_data)
    available = len(set(system_graph.descriptions) - exclude_set)
    print(f"Exclusions: {len(exclude_set)} nodes ({len(tool_nodes)} tool + {len(exclude_set) - len(tool_nodes)} non-flavor)")
    print(f"Available: {available} descriptors")

    # Load existing questions and inject audit status for the generator
    master_file = Path("data/questions/all_questions_system.json")
    audit_state_file = Path("data/audit_results/audit_state.json")
    existing_questions = []
    if master_file.exists():
        with open(master_file) as f:
            master_data = json.load(f)
        audit_state = {}
        if audit_state_file.exists():
            with open(audit_state_file) as f:
                audit_state = json.load(f)
        # Inject _audit_status so generator knows which questions are confirmed
        existing_questions = []
        for q in master_data.get('questions', []):
            q = dict(q)
            q['_audit_status'] = audit_state.get(q['id'], {}).get('status', 'pending')
            existing_questions.append(q)
        print(f"Existing questions: {len(existing_questions)}")

    # Determine seed
    seed = args.seed if args.seed is not None else 42
    if not generating_all and args.seed is None:
        # Use a time-based seed for partial generation to avoid repeating same results
        seed = int(datetime.now().timestamp()) % 100000
        print(f"Using time-based seed: {seed} (override with --seed)")

    # Create generator
    generator = QuestionGenerator(
        system_graph,
        random_seed=seed,
        exclude_descriptors=exclude_set,
        tool_graph_nodes=tool_nodes,
        existing_questions=existing_questions,
    )

    # Generate
    short_names = [k for k, v in TASK_TYPE_MAP.items() if v in task_types]
    print(f"\nGenerating: {', '.join(short_names)}")
    print("=" * 60)

    questions = []
    for tt in task_types:
        section, key = TASK_CONFIG_SECTION[tt]
        config = generator.config.get(section, {}).get(key, {})
        if not config:
            print(f"  {tt}: no config found, skipping")
            continue

        if args.count is not None:
            config = dict(config)  # copy to avoid mutating
            config['count'] = args.count

        result = generator.generate_category(tt, config)
        short = tt.split('_')[0]
        print(f"  {short}: {len(result)} generated (count={config.get('count', '?')})")
        questions.extend(result)

    print(f"\nTotal generated: {len(questions)}")

    if not questions:
        print("No questions generated.")
        return 0

    # Deduplicate
    unique_questions, duplicates = generator.deduplicate_questions(questions, by_field='descriptor')
    if duplicates:
        print(f"Removed {len(duplicates)} duplicates")
    questions = unique_questions

    # Append to master file
    if master_file.exists() and existing_questions:
        existing_ids = {q['id'] for q in master_data['questions']}
        new_only = [q for q in questions if q['id'] not in existing_ids]
        master_data['questions'].extend(new_only)
        master_data['metadata']['total_questions'] = len(master_data['questions'])
        master_data['metadata']['last_modified'] = datetime.now().isoformat()
        backup_before_write(master_file)
        with open(master_file, 'w') as f:
            json.dump(master_data, f, indent=2)
        print(f"Appended {len(new_only)} new questions (skipped {len(questions) - len(new_only)} existing)")
    else:
        generator.save_questions(questions, str(master_file))
        print(f"Saved {len(questions)} questions to {master_file}")

    # Summary
    task_counts = Counter(q['task_type'] for q in questions)
    print(f"\nBreakdown:")
    for tt in task_types:
        c = task_counts.get(tt, 0)
        short = tt.split('_')[0]
        print(f"  {short}: {c}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
