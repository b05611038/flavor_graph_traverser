"""
Restore recovered A1/A2 questions with new UUID IDs.

This script:
1. Loads recovered A1/A2 questions
2. Assigns new UUID-based IDs
3. Adds them to main questions file
4. Updates audit state to mark them as confirmed
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

def generate_uuid_id(task_type: str) -> str:
    """Generate UUID-based ID."""
    uuid_str = str(uuid.uuid4()).replace('-', '')[:8]
    return f"{task_type}_{uuid_str}"

def main():
    # Paths
    recovered_path = Path("data/questions/recovered_confirmed_questions.json")
    questions_path = Path("data/questions/all_questions_system.json")
    audit_path = Path("data/audit_results/audit_state.json")

    # Load recovered questions
    print("Loading recovered questions...")
    with open(recovered_path) as f:
        recovered = json.load(f)

    a1_questions = recovered['A1_confirmed']
    a2_questions = recovered['A2_confirmed']

    print(f"  A1: {len(a1_questions)} questions")
    print(f"  A2: {len(a2_questions)} questions")

    # Load current questions
    print("\nLoading current questions...")
    with open(questions_path) as f:
        questions_data = json.load(f)

    current_count = len(questions_data['questions'])
    print(f"  Current: {current_count} questions")

    # Load audit state
    print("\nLoading audit state...")
    with open(audit_path) as f:
        audit_state = json.load(f)

    # Create ID mapping: old_id -> new_uuid_id
    id_mapping = {}
    restored_questions = []

    # Process A1 questions
    print("\nRestoring A1 questions with new UUID IDs...")
    for old_q in a1_questions:
        old_id = old_q['id']
        new_id = generate_uuid_id(old_q['task_type'])
        id_mapping[old_id] = new_id

        # Create new question with UUID
        new_q = old_q.copy()
        new_q['id'] = new_id
        restored_questions.append(new_q)

    # Process A2 questions
    print(f"Restored {len(restored_questions)} A1 questions")
    print("\nRestoring A2 questions with new UUID IDs...")
    a2_start = len(restored_questions)
    for old_q in a2_questions:
        old_id = old_q['id']
        new_id = generate_uuid_id(old_q['task_type'])
        id_mapping[old_id] = new_id

        # Create new question with UUID
        new_q = old_q.copy()
        new_q['id'] = new_id
        restored_questions.append(new_q)

    print(f"Restored {len(restored_questions) - a2_start} A2 questions")

    # Add to questions file
    print(f"\nAdding {len(restored_questions)} questions to questions file...")
    questions_data['questions'].extend(restored_questions)

    # Create backup
    backup_path = questions_path.with_suffix(f'.json.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    print(f"Creating backup: {backup_path}")
    with open(backup_path, 'w') as f:
        json.dump(questions_data, f, indent=2)

    # Write updated questions
    with open(questions_path, 'w') as f:
        json.dump(questions_data, f, indent=2)

    print(f"  New total: {len(questions_data['questions'])} questions")

    # Update audit state
    print("\nUpdating audit state for restored questions...")
    timestamp = datetime.now().isoformat()

    for old_id, new_id in id_mapping.items():
        # Create confirmed audit entry
        audit_state[new_id] = {
            "question_id": new_id,
            "status": "confirmed",
            "timestamp": timestamp,
            "notes": f"Restored from backup (originally {old_id})"
        }

    # Save audit state
    audit_backup = audit_path.with_suffix(f'.json.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    print(f"Creating audit backup: {audit_backup}")
    with open(audit_backup, 'w') as f:
        json.dump(audit_state, f, indent=2)

    with open(audit_path, 'w') as f:
        json.dump(audit_state, f, indent=2)

    print(f"  Added {len(id_mapping)} confirmed entries")

    # Summary
    print("\n" + "="*70)
    print("RESTORATION COMPLETE")
    print("="*70)
    print(f"Restored questions: {len(restored_questions)}")
    print(f"  A1: {len(a1_questions)}")
    print(f"  A2: {len(a2_questions)}")
    print(f"\nNew question count: {len(questions_data['questions'])}")
    print(f"New confirmed count: {len([s for s in audit_state.values() if isinstance(s, dict) and s.get('status') == 'confirmed'])}")

    # Save ID mapping for reference
    mapping_path = Path("data/audit_results/id_mapping_restored.json")
    with open(mapping_path, 'w') as f:
        json.dump(id_mapping, f, indent=2)
    print(f"\nID mapping saved to: {mapping_path}")

if __name__ == "__main__":
    main()
