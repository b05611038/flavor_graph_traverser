"""
Add additional 15 A2 questions found in backup.
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
    # Load the 15 additional questions
    with open('data/questions/a2_recovered_from_backup.json') as f:
        data = json.load(f)

    additional_questions = data['questions']
    print(f"Loading {len(additional_questions)} additional A2 questions from backup")

    # Load current questions
    with open('data/questions/all_questions_system.json') as f:
        questions_data = json.load(f)

    current_count = len(questions_data['questions'])
    print(f"Current question count: {current_count}")

    # Load audit state
    with open('data/audit_results/audit_state.json') as f:
        audit_state = json.load(f)

    # Assign new UUIDs and add questions
    id_mapping = {}
    timestamp = datetime.now().isoformat()

    for old_q in additional_questions:
        old_id = old_q['id']
        new_id = generate_uuid_id(old_q['task_type'])
        id_mapping[old_id] = new_id

        # Create new question with UUID
        new_q = old_q.copy()
        new_q['id'] = new_id
        questions_data['questions'].append(new_q)

        # Add to audit state as confirmed
        audit_state[new_id] = {
            "question_id": new_id,
            "status": "confirmed",
            "timestamp": timestamp,
            "notes": f"Additional recovery from backup (originally {old_id})"
        }

    # Save updated questions
    backup_path = Path('data/questions/all_questions_system.json.backup_add_a2')
    with open(backup_path, 'w') as f:
        json.dump(questions_data, f, indent=2)

    with open('data/questions/all_questions_system.json', 'w') as f:
        json.dump(questions_data, f, indent=2)

    print(f"Added {len(additional_questions)} questions")
    print(f"New total: {len(questions_data['questions'])}")

    # Save audit state
    audit_backup = Path('data/audit_results/audit_state.json.backup_add_a2')
    with open(audit_backup, 'w') as f:
        json.dump(audit_state, f, indent=2)

    with open('data/audit_results/audit_state.json', 'w') as f:
        json.dump(audit_state, f, indent=2)

    # Check confirmed counts
    confirmed_by_type = {}
    for qid, state in audit_state.items():
        if isinstance(state, dict) and state.get('status') == 'confirmed':
            q = next((q for q in questions_data['questions'] if q['id'] == qid), None)
            if q:
                task_type = q['task_type'].split('_')[0]
                confirmed_by_type[task_type] = confirmed_by_type.get(task_type, 0) + 1

    print("\nConfirmed questions by type:")
    for task_type in sorted(confirmed_by_type.keys()):
        print(f"  {task_type}: {confirmed_by_type[task_type]}")

    # Save ID mapping
    with open('data/audit_results/id_mapping_additional_a2.json', 'w') as f:
        json.dump(id_mapping, f, indent=2)

    print(f"\nID mapping saved to: data/audit_results/id_mapping_additional_a2.json")

if __name__ == "__main__":
    main()
