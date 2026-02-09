"""
Remove duplicate questions from the confirmed set.

Keeps the first occurrence of each unique question (by descriptor+ancestor+answer).
"""

import json
from collections import defaultdict
from pathlib import Path

def main():
    # Load questions and audit state
    with open('data/questions/all_questions_system.json') as f:
        questions_data = json.load(f)

    with open('data/audit_results/audit_state.json') as f:
        audit_state = json.load(f)

    # Get confirmed questions
    confirmed_ids = {qid for qid, state in audit_state.items()
                     if isinstance(state, dict) and state.get('status') == 'confirmed'}

    # Find duplicates for A1
    a1_questions = [q for q in questions_data['questions']
                    if q['id'] in confirmed_ids and q.get('task_type', '').startswith('A1_')]

    a1_by_descriptor = defaultdict(list)
    for q in a1_questions:
        descriptor = q.get('_objects', {}).get('descriptor', 'UNKNOWN')
        a1_by_descriptor[descriptor].append(q)

    a1_to_remove = set()
    for descriptor, questions in a1_by_descriptor.items():
        if len(questions) > 1:
            # Keep first, remove rest
            for q in questions[1:]:
                a1_to_remove.add(q['id'])

    # Find duplicates for A2
    a2_questions = [q for q in questions_data['questions']
                    if q['id'] in confirmed_ids and q.get('task_type', '').startswith('A2_')]

    a2_by_pair = defaultdict(list)
    for q in a2_questions:
        objects = q.get('_objects', {})
        descriptor = objects.get('descriptor', 'UNKNOWN')
        ancestor = objects.get('ancestor', 'UNKNOWN')
        is_ancestor = objects.get('is_ancestor', 'UNKNOWN')
        key = f"{descriptor}|{ancestor}|{is_ancestor}"
        a2_by_pair[key].append(q)

    a2_to_remove = set()
    for key, questions in a2_by_pair.items():
        if len(questions) > 1:
            # Keep first, remove rest
            for q in questions[1:]:
                a2_to_remove.add(q['id'])

    # Remove duplicates
    to_remove = a1_to_remove | a2_to_remove

    print(f"Duplicate questions to remove:")
    print(f"  A1: {len(a1_to_remove)}")
    print(f"  A2: {len(a2_to_remove)}")
    print(f"  Total: {len(to_remove)}")

    if not to_remove:
        print("\nNo duplicates to remove!")
        return

    # Remove from questions list
    original_count = len(questions_data['questions'])
    questions_data['questions'] = [q for q in questions_data['questions']
                                   if q['id'] not in to_remove]

    removed_count = original_count - len(questions_data['questions'])
    print(f"\nRemoved {removed_count} questions from questions list")

    # Update audit state - mark as deleted
    for qid in to_remove:
        if qid in audit_state:
            audit_state[qid]['status'] = 'deleted'
            audit_state[qid]['notes'] = (audit_state[qid].get('notes', '') +
                                         ' [DUPLICATE - removed]')

    # Create backups
    backup_path = Path('data/questions/all_questions_system.json.backup_dedup')
    with open(backup_path, 'w') as f:
        json.dump(questions_data, f, indent=2)

    audit_backup = Path('data/audit_results/audit_state.json.backup_dedup')
    with open(audit_backup, 'w') as f:
        json.dump(audit_state, f, indent=2)

    # Save updated files
    with open('data/questions/all_questions_system.json', 'w') as f:
        json.dump(questions_data, f, indent=2)

    with open('data/audit_results/audit_state.json', 'w') as f:
        json.dump(audit_state, f, indent=2)

    # Report final counts
    confirmed_ids = {qid for qid, state in audit_state.items()
                     if isinstance(state, dict) and state.get('status') == 'confirmed'}

    final_a1 = len([q for q in questions_data['questions']
                    if q['id'] in confirmed_ids and q.get('task_type', '').startswith('A1_')])
    final_a2 = len([q for q in questions_data['questions']
                    if q['id'] in confirmed_ids and q.get('task_type', '').startswith('A2_')])
    final_a3 = len([q for q in questions_data['questions']
                    if q['id'] in confirmed_ids and q.get('task_type', '').startswith('A3_')])

    print("\n" + "="*70)
    print("DEDUPLICATION COMPLETE")
    print("="*70)
    print(f"Final confirmed counts:")
    print(f"  A1: {final_a1}")
    print(f"  A2: {final_a2}")
    print(f"  A3: {final_a3}")
    print(f"\nTotal questions: {len(questions_data['questions'])}")

if __name__ == "__main__":
    main()
