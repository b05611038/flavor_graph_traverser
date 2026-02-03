#!/usr/bin/env python3
"""
Filter questions to keep only confirmed ones.

Usage:
    # Filter by task type (e.g., keep only confirmed A1 questions)
    python scripts/filter_confirmed_questions.py --task-type A1_root_classification

    # Filter all questions (keep only confirmed from all categories)
    python scripts/filter_confirmed_questions.py --all
"""

import json
import argparse
from pathlib import Path
from datetime import datetime


def load_questions(file_path: str):
    """Load questions from JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def load_audit_state(file_path: str):
    """Load audit state from JSON file."""
    if not Path(file_path).exists():
        return {}
    with open(file_path, 'r') as f:
        return json.load(f)


def filter_questions(questions_data, audit_state, task_type=None):
    """
    Filter questions to keep only confirmed ones.

    Args:
        questions_data: Full questions dict with metadata and questions
        audit_state: Audit state dict
        task_type: If specified, only filter this task type (e.g., "A1_root_classification")

    Returns:
        Filtered questions data with updated metadata
    """
    all_questions = questions_data['questions']
    confirmed_ids = {qid for qid, state in audit_state.items() if state['status'] == 'confirmed'}

    # Filter questions
    if task_type:
        # Keep confirmed from this task type, keep all from other task types
        filtered_questions = [
            q for q in all_questions
            if (q['task_type'] == task_type and q['id'] in confirmed_ids) or
               (q['task_type'] != task_type)
        ]
        print(f"\nFiltering {task_type}:")
        task_questions = [q for q in all_questions if q['task_type'] == task_type]
        confirmed_count = len([q for q in task_questions if q['id'] in confirmed_ids])
        print(f"  Total candidates: {len(task_questions)}")
        print(f"  Confirmed: {confirmed_count}")
        print(f"  Filtered out: {len(task_questions) - confirmed_count}")
    else:
        # Keep only confirmed from all task types
        filtered_questions = [q for q in all_questions if q['id'] in confirmed_ids]
        print(f"\nFiltering all questions:")
        print(f"  Total candidates: {len(all_questions)}")
        print(f"  Confirmed: {len(filtered_questions)}")
        print(f"  Filtered out: {len(all_questions) - len(filtered_questions)}")

    # Update metadata
    from collections import Counter
    task_counts = Counter(q['task_type'] for q in filtered_questions)
    category_counts = Counter(q['category'] for q in filtered_questions)

    filtered_data = {
        'metadata': {
            'total_count': len(filtered_questions),
            'by_category': dict(category_counts),
            'by_task_type': dict(task_counts),
            'random_seed': questions_data['metadata']['random_seed'],
            'generated_at': questions_data['metadata']['generated_at'],
            'filtered_at': datetime.now().isoformat(),
            'filter_type': task_type if task_type else 'all'
        },
        'questions': filtered_questions
    }

    return filtered_data


def main():
    parser = argparse.ArgumentParser(description='Filter questions to keep only confirmed ones')
    parser.add_argument('--task-type', type=str,
                       help='Task type to filter (e.g., A1_root_classification). If not specified, filters all.')
    parser.add_argument('--questions', type=str,
                       default='data/questions/all_questions_system.json',
                       help='Path to questions JSON file')
    parser.add_argument('--audit-state', type=str,
                       default='data/audit_state.json',
                       help='Path to audit state JSON file')
    parser.add_argument('--output', type=str,
                       help='Output file path (default: overwrites input file)')
    parser.add_argument('--backup', action='store_true',
                       help='Create backup of original file')

    args = parser.parse_args()

    # Load data
    print(f"Loading questions from: {args.questions}")
    questions_data = load_questions(args.questions)

    print(f"Loading audit state from: {args.audit_state}")
    audit_state = load_audit_state(args.audit_state)

    print(f"Audit state: {len(audit_state)} reviewed questions")
    confirmed_count = len([s for s in audit_state.values() if s['status'] == 'confirmed'])
    flagged_count = len([s for s in audit_state.values() if s['status'] == 'flagged'])
    print(f"  Confirmed: {confirmed_count}")
    print(f"  Flagged: {flagged_count}")

    # Filter
    filtered_data = filter_questions(questions_data, audit_state, args.task_type)

    # Save
    output_path = args.output if args.output else args.questions

    if args.backup and output_path == args.questions:
        backup_path = args.questions.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        print(f"\nCreating backup: {backup_path}")
        with open(backup_path, 'w') as f:
            json.dump(questions_data, f, indent=2)

    print(f"\nSaving filtered questions to: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(filtered_data, f, indent=2)

    print("\n✓ Filtering complete!")
    print(f"  Final question count: {filtered_data['metadata']['total_count']}")
    print("\nBreakdown by task type:")
    for task_type, count in sorted(filtered_data['metadata']['by_task_type'].items()):
        print(f"  {task_type}: {count}")


if __name__ == '__main__':
    main()
