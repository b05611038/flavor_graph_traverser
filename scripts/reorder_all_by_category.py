#!/usr/bin/env python3
"""
Reorder ALL pending questions to prioritize under-represented root categories.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from collections import Counter


def get_roots_from_question(q):
    """Extract root categories from any question type."""
    task_type = q['task_type']

    if task_type == 'A1_root_classification':
        return q.get('_objects', {}).get('all_valid_roots', [])
    elif task_type == 'A2_ancestor_verification':
        # Get descriptor's roots
        desc = q.get('_objects', {}).get('descriptor', '')
        return q.get('_objects', {}).get('descriptor_roots', [])
    elif task_type == 'A3_sibling_identification':
        desc = q.get('_objects', {}).get('descriptor', '')
        return q.get('_objects', {}).get('descriptor_roots', [])
    elif task_type == 'A4_path_reconstruction':
        desc = q.get('_objects', {}).get('descriptor', '')
        # Try to extract from path
        path = q.get('_objects', {}).get('correct_path', [])
        if len(path) > 1:
            return [path[1]]  # Second element is usually root
        return []
    elif task_type == 'A5_lca_finding':
        # Get both descriptors' roots
        roots = []
        for key in ['descriptor1_roots', 'descriptor2_roots']:
            roots.extend(q.get('_objects', {}).get(key, []))
        return list(set(roots))
    elif task_type in ['E1_similarity_ranking', 'E2_pairwise_comparison', 'E3_odd_one_out']:
        # Get target descriptor roots
        target = q.get('_objects', {}).get('target', '')
        return q.get('_objects', {}).get('target_roots', [])
    elif task_type == 'F_flavor_description':
        # Get descriptor roots
        desc = q.get('_objects', {}).get('descriptor', '')
        return q.get('_objects', {}).get('descriptor_roots', [])

    return []


def main():
    # Load questions
    questions_file = 'data/questions/all_questions_system.json'
    with open(questions_file, 'r') as f:
        data = json.load(f)

    # Load audit state
    audit_state_file = 'data/audit_state.json'
    if Path(audit_state_file).exists():
        with open(audit_state_file, 'r') as f:
            audit_state = json.load(f)
    else:
        audit_state = {}

    reviewed_ids = set(audit_state.keys())

    # Separate reviewed and pending
    all_questions = data['questions']
    reviewed = [q for q in all_questions if q['id'] in reviewed_ids]
    pending = [q for q in all_questions if q['id'] not in reviewed_ids]

    print(f'Questions:')
    print(f'  Reviewed: {len(reviewed)}')
    print(f'  Pending: {len(pending)}')
    print()

    # Priority order (least represented first)
    priority_order = [
        'floral',           # 1
        'sour/fermented',   # 1
        'nutty/cocoa',      # 2
        'spices',           # 3
        'green/vegetable',  # 4
        'other',            # 5
        'roasted',          # 6
        'sweet',            # 13 (over)
        'fruity'            # 14 (over)
    ]

    # Score each pending question
    def score_question(q):
        roots = get_roots_from_question(q)
        if not roots:
            return 999  # Push to end

        # Get minimum priority index (highest priority)
        min_priority = min([priority_order.index(root) if root in priority_order else 999
                           for root in roots])
        return min_priority

    # Sort pending by priority
    pending_sorted = sorted(pending, key=score_question)

    print('Reordered pending questions by category priority:')
    print('(Showing first 30)')
    print('-'*80)
    for i, q in enumerate(pending_sorted[:30], 1):
        task = q['task_type']

        # Get descriptor/description
        if task == 'A1_root_classification':
            desc = q.get('_objects', {}).get('descriptor', 'N/A')
            roots = q.get('_objects', {}).get('all_valid_roots', [])
        else:
            desc = q.get('_objects', {}).get('descriptor',
                   q.get('_objects', {}).get('target',
                   q.get('text', '')[:30]))
            roots = get_roots_from_question(q)

        priority = score_question(q)
        print(f'{i:2d}. [{task:25s}] {desc:30s} → {roots} (p:{priority})')
    print()

    # Count rare categories in first 50 pending
    rare_count = 0
    for q in pending_sorted[:50]:
        roots = get_roots_from_question(q)
        if any(r in ['floral', 'sour/fermented', 'nutty/cocoa', 'spices'] for r in roots):
            rare_count += 1

    print(f'In first 50 pending questions: {rare_count} contain rare categories')
    print()

    # Reassemble all questions
    all_questions_reordered = reviewed + pending_sorted

    # Update metadata
    task_counts = Counter(q['task_type'] for q in all_questions_reordered)
    category_counts = Counter(q['category'] for q in all_questions_reordered)

    data['metadata']['total_count'] = len(all_questions_reordered)
    data['metadata']['by_category'] = dict(category_counts)
    data['metadata']['by_task_type'] = dict(task_counts)
    data['questions'] = all_questions_reordered

    # Save
    print(f'Saving reordered questions...')
    with open(questions_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f'\n✓ Complete!')
    print(f'All pending questions now prioritize rare categories:')
    print(f'  floral, sour/fermented, nutty/cocoa, spices')


if __name__ == '__main__':
    main()
