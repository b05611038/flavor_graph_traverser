#!/usr/bin/env python3
"""
Reorder A2 questions to prioritize non-ROOT:SYSTEM questions.
ROOT:SYSTEM ancestor questions are often trivial (everything is under ROOT:SYSTEM).
"""

import json
from datetime import datetime

def reorder_a2_questions():
    """Reorder questions to put interesting A2 questions first."""

    # Load questions
    questions_file = "data/questions/all_questions_system.json"
    print(f"Loading questions from: {questions_file}")

    with open(questions_file) as f:
        data = json.load(f)

    questions = data['questions']

    # Separate into categories
    a2_root_system = []  # A2 with ROOT:SYSTEM ancestor - boring
    a2_other = []  # A2 with interesting ancestors
    non_a2 = []  # Everything else

    for q in questions:
        if q['task_type'] == 'A2_ancestor_verification':
            ancestor = q['_objects'].get('ancestor', '')
            if ancestor == 'ROOT:SYSTEM':
                a2_root_system.append(q)
            else:
                a2_other.append(q)
        else:
            non_a2.append(q)

    # New order: Interesting A2 first, ROOT:SYSTEM A2 at back, everything else after
    reordered = a2_other + non_a2 + a2_root_system

    print(f"\nReordered:")
    print(f"  A2 (non-ROOT:SYSTEM): {len(a2_other)} - Priority")
    print(f"  Non-A2 questions: {len(non_a2)}")
    print(f"  A2 (ROOT:SYSTEM): {len(a2_root_system)} - Deprioritized")

    # Update data
    data['questions'] = reordered
    data['metadata']['last_modified'] = datetime.now().isoformat()

    # Save
    with open(questions_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Saved reordered questions to: {questions_file}")


if __name__ == "__main__":
    reorder_a2_questions()
