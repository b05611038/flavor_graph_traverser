#!/usr/bin/env python3
"""
Reorder pending A1 questions to prioritize under-represented root categories.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from collections import Counter


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

    # Separate questions
    all_questions = data['questions']
    a1_questions = [q for q in all_questions if q['task_type'] == 'A1_root_classification']
    other_questions = [q for q in all_questions if q['task_type'] != 'A1_root_classification']

    # Separate reviewed and pending A1
    reviewed_a1 = [q for q in a1_questions if q['id'] in reviewed_ids]
    pending_a1 = [q for q in a1_questions if q['id'] not in reviewed_ids]

    print(f'A1 questions:')
    print(f'  Reviewed: {len(reviewed_a1)}')
    print(f'  Pending: {len(pending_a1)}')
    print()

    # Calculate current coverage from reviewed questions
    confirmed_ids = [qid for qid, state in audit_state.items() if state['status'] == 'confirmed']
    confirmed_a1 = [q for q in reviewed_a1 if q['id'] in confirmed_ids]

    root_counts = Counter()
    for q in confirmed_a1:
        valid_roots = q.get('_objects', {}).get('all_valid_roots', [])
        for root in valid_roots:
            root_counts[root] += 1

    print('Current confirmed root coverage:')
    for root, count in sorted(root_counts.items(), key=lambda x: x[1]):
        print(f'  {root}: {count}')
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

    # Score each pending question based on priority
    def score_question(q):
        valid_roots = q.get('_objects', {}).get('all_valid_roots', [])
        if not valid_roots:
            return 999  # Push to end

        # Get minimum priority index (highest priority)
        min_priority = min([priority_order.index(root) if root in priority_order else 999
                           for root in valid_roots])
        return min_priority

    # Sort pending by priority
    pending_a1_sorted = sorted(pending_a1, key=score_question)

    print('Reordered pending A1 questions by priority:')
    print('(Showing first 20)')
    print('-'*70)
    for i, q in enumerate(pending_a1_sorted[:20], 1):
        desc = q.get('_objects', {}).get('descriptor', 'N/A')
        valid_roots = q.get('_objects', {}).get('all_valid_roots', [])
        priority = score_question(q)
        print(f'{i:2d}. {desc:30s} {valid_roots} (priority: {priority})')
    print()

    # Reassemble all questions
    all_questions_reordered = reviewed_a1 + pending_a1_sorted + other_questions

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
    print(f'Pending A1 questions now prioritize under-represented categories')
    print(f'You will see floral, sour/fermented, nutty/cocoa, spices first')


if __name__ == '__main__':
    main()
