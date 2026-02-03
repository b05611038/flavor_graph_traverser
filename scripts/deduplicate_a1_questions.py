#!/usr/bin/env python3
"""
Remove duplicate descriptors from A1 questions.
Keeps first occurrence, removes subsequent duplicates.
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

    # Separate A1 and other questions
    a1_questions = [q for q in data['questions'] if q['task_type'] == 'A1_root_classification']
    other_questions = [q for q in data['questions'] if q['task_type'] != 'A1_root_classification']

    print(f"Total A1 questions: {len(a1_questions)}")

    # Find duplicates
    descriptors = [q.get('_objects', {}).get('descriptor', '') for q in a1_questions]
    descriptor_counts = Counter(descriptors)
    duplicates = {desc: count for desc, count in descriptor_counts.items() if count > 1}

    print(f"Duplicate descriptors: {len(duplicates)}")
    if duplicates:
        print("\nDuplicates:")
        for desc, count in sorted(duplicates.items()):
            print(f"  {desc}: {count} times")

    # Deduplicate: keep first occurrence of each descriptor
    seen_descriptors = set()
    deduplicated_a1 = []
    removed_count = 0

    for q in a1_questions:
        descriptor = q.get('_objects', {}).get('descriptor', '')

        if descriptor not in seen_descriptors:
            seen_descriptors.add(descriptor)
            deduplicated_a1.append(q)
        else:
            # Skip duplicate, unless it's reviewed (don't remove reviewed questions)
            if q['id'] in reviewed_ids:
                print(f"\nWarning: Duplicate reviewed question found: {q['id']} ({descriptor})")
                print(f"  Keeping it since it's already reviewed")
                deduplicated_a1.append(q)
            else:
                removed_count += 1
                print(f"  Removing duplicate (pending): {q['id']} ({descriptor})")

    print(f"\nRemoved {removed_count} duplicate questions")
    print(f"Remaining A1 questions: {len(deduplicated_a1)}")

    # Reassemble all questions
    all_questions = deduplicated_a1 + other_questions

    # Update metadata
    task_counts = Counter(q['task_type'] for q in all_questions)
    category_counts = Counter(q['category'] for q in all_questions)

    data['metadata']['total_count'] = len(all_questions)
    data['metadata']['by_category'] = dict(category_counts)
    data['metadata']['by_task_type'] = dict(task_counts)
    data['questions'] = all_questions

    # Save
    print(f"\nSaving deduplicated questions...")
    with open(questions_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Complete!")
    print(f"  Total questions: {len(all_questions)}")
    print(f"  A1 questions: {len(deduplicated_a1)} (all unique descriptors)")


if __name__ == '__main__':
    main()
