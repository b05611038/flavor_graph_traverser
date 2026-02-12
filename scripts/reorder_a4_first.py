#!/usr/bin/env python3
"""Reorder queue to put A4 questions first for auditing."""

import json

# Load all questions
with open('data/questions/all_questions_system.json', 'r') as f:
    data = json.load(f)
    all_questions = data['questions']
    metadata = data['metadata']

# Load audit state
with open('data/audit_results/audit_state.json', 'r') as f:
    state = json.load(f)

print("Reordering questions to prioritize A4...")
print()

# Separate questions by status and type
a4_pending = []
other_pending = []

for q in all_questions:
    qid = q['id']
    status = state.get(qid, {}).get('status', 'pending')

    if status == 'pending':
        if 'A4' in q.get('task_type', ''):
            a4_pending.append(q)
        else:
            other_pending.append(q)

# Get confirmed and flagged questions
confirmed = [q for q in all_questions if state.get(q['id'], {}).get('status') == 'confirmed']
flagged = [q for q in all_questions if state.get(q['id'], {}).get('status') == 'flagged']

print(f"Found:")
print(f"  Confirmed: {len(confirmed)}")
print(f"  Flagged: {len(flagged)}")
print(f"  A4 pending: {len(a4_pending)}")
print(f"  Other pending: {len(other_pending)}")
print()

# Reorder: confirmed, flagged, A4 pending, other pending
reordered = confirmed + flagged + a4_pending + other_pending

print(f"New order: confirmed ({len(confirmed)}) → flagged ({len(flagged)}) → A4 pending ({len(a4_pending)}) → other pending ({len(other_pending)})")
print()

# Update metadata
import datetime
metadata['total_questions'] = len(reordered)
metadata['last_modified'] = datetime.datetime.now().isoformat()

# Save
output_data = {
    'metadata': metadata,
    'questions': reordered
}

with open('data/questions/all_questions_system.json', 'w') as f:
    json.dump(output_data, f, indent=2)

print("✓ Saved reordered questions")
print()
print("Next pending questions:")
pending_count = 0
for q in reordered:
    if state.get(q['id'], {}).get('status', 'pending') == 'pending':
        pending_count += 1
        if pending_count <= 5:
            print(f"  {pending_count}. [{q['task_type']}] {q['_objects'].get('descriptor', 'N/A')}")
        if pending_count == 5:
            break
