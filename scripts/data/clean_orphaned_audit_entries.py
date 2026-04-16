"""
Clean orphaned entries from audit_state.json.

Removes audit entries for questions that don't exist in the questions file.
This happens after ID migrations or question deletions.
"""

import json
from pathlib import Path
from datetime import datetime

def main():
    # Load files
    with open('data/audit_results/audit_state.json') as f:
        audit_state = json.load(f)

    with open('data/questions/all_questions_system.json') as f:
        questions_data = json.load(f)

    # Get existing question IDs
    existing_ids = {q['id'] for q in questions_data['questions']}

    print(f"Total audit entries: {len(audit_state)}")
    print(f"Existing questions: {len(existing_ids)}")

    # Find orphaned entries
    orphaned = {}
    for qid, state in audit_state.items():
        if qid not in existing_ids:
            orphaned[qid] = state

    print(f"\nOrphaned entries: {len(orphaned)}")

    # Show breakdown by status
    from collections import Counter
    orphaned_by_status = Counter()
    for state in orphaned.values():
        if isinstance(state, dict):
            orphaned_by_status[state.get('status', 'unknown')] += 1

    print("\nOrphaned by status:")
    for status, count in sorted(orphaned_by_status.items()):
        print(f"  {status}: {count}")

    # Backup before cleaning
    backup_path = Path('data/audit_results/audit_state.json.backup_clean_orphaned')
    with open(backup_path, 'w') as f:
        json.dump(audit_state, f, indent=2)
    print(f"\nBackup created: {backup_path}")

    # Remove orphaned entries
    cleaned_audit = {qid: state for qid, state in audit_state.items()
                     if qid in existing_ids}

    print(f"\nAfter cleaning:")
    print(f"  Total entries: {len(cleaned_audit)}")

    # Save cleaned audit state
    with open('data/audit_results/audit_state.json', 'w') as f:
        json.dump(cleaned_audit, f, indent=2)

    # Show final counts
    final_counts = Counter()
    for state in cleaned_audit.values():
        if isinstance(state, dict):
            final_counts[state.get('status', 'unknown')] += 1

    print("\nFinal counts:")
    for status, count in sorted(final_counts.items()):
        print(f"  {status}: {count}")

    print("\n✓ Audit state cleaned!")

if __name__ == "__main__":
    main()
