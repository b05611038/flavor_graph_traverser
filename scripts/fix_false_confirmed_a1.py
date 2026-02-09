"""
Remove false 'confirmed' status from 31 A1 questions that were never actually reviewed.

These questions were created during regeneration and incorrectly inherited
'confirmed' status. User only confirmed 50 A1 questions, which we restored.
"""

import json
from pathlib import Path

def main():
    # Load data
    with open('data/questions/all_questions_system.json') as f:
        questions_data = json.load(f)

    with open('data/audit_results/audit_state.json') as f:
        audit_state = json.load(f)

    # Find the 31 false confirmed A1 questions
    confirmed_ids = {qid for qid, state in audit_state.items()
                     if isinstance(state, dict) and state.get('status') == 'confirmed'}

    a1_questions = [q for q in questions_data['questions']
                    if q['id'] in confirmed_ids and q.get('task_type', '').startswith('A1_')]

    # These are the ones with "Audited and confirmed in previous session"
    # but were NOT actually confirmed by the user
    false_confirmed = [q for q in a1_questions
                       if 'Audited and confirmed' in audit_state[q['id']].get('notes', '')]

    print(f"Found {len(false_confirmed)} A1 questions with false 'confirmed' status")
    print("\nSample descriptors:")
    for q in false_confirmed[:10]:
        desc = q.get('_objects', {}).get('descriptor', 'UNKNOWN')
        print(f"  - {desc}")

    # Update their status to 'pending'
    for q in false_confirmed:
        qid = q['id']
        audit_state[qid]['status'] = 'pending'
        audit_state[qid]['notes'] = 'Auto-generated during regeneration - needs review'

    # Create backup
    backup_path = Path('data/audit_results/audit_state.json.backup_fix_a1')
    with open(backup_path, 'w') as f:
        json.dump(audit_state, f, indent=2)

    # Save fixed audit state
    with open('data/audit_results/audit_state.json', 'w') as f:
        json.dump(audit_state, f, indent=2)

    # Report final counts
    confirmed_ids_after = {qid for qid, state in audit_state.items()
                           if isinstance(state, dict) and state.get('status') == 'confirmed'}

    final_a1 = len([q for q in questions_data['questions']
                    if q['id'] in confirmed_ids_after and q.get('task_type', '').startswith('A1_')])
    final_a2 = len([q for q in questions_data['questions']
                    if q['id'] in confirmed_ids_after and q.get('task_type', '').startswith('A2_')])
    final_a3 = len([q for q in questions_data['questions']
                    if q['id'] in confirmed_ids_after and q.get('task_type', '').startswith('A3_')])

    print("\n" + "="*70)
    print("STATUS FIXED")
    print("="*70)
    print(f"Marked {len(false_confirmed)} A1 questions as 'pending'")
    print(f"\nFinal confirmed counts:")
    print(f"  A1: {final_a1}")
    print(f"  A2: {final_a2}")
    print(f"  A3: {final_a3}")

if __name__ == "__main__":
    main()
