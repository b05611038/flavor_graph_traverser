#!/usr/bin/env python3
"""
Queue Manager CLI

Easy command-line interface for managing the question review queue.

Usage:
    python scripts/manage_queue.py status           # Show queue statistics
    python scripts/manage_queue.py preview          # Show next 20 questions for auditor
    python scripts/manage_queue.py prioritize A2    # Move A2 pending/flagged to front
    python scripts/manage_queue.py deprioritize A1  # Move A1 to back
    python scripts/manage_queue.py clear A1         # Move all A1 to back (completed)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from FlavorGraphTraverser.evaluation.queue_manager import QueueManager


# Task type mapping (abbreviation -> full name)
TASK_TYPES = {
    'A1': 'A1_root_classification',
    'A2': 'A2_ancestor_verification',
    'A3': 'A3_sibling_identification',
    'A4': 'A4_path_reconstruction',
    'A5': 'A5_lca_finding',
    'E1': 'E1_similarity_ranking',
    'E2': 'E2_pairwise_comparison',
    'E3': 'E3_odd_one_out',
    'F': 'F_flavor_description',
}


def show_status(qm: QueueManager):
    """Show queue statistics."""
    print("\n" + "=" * 70)
    print("Queue Status")
    print("=" * 70)

    stats = qm.get_stats()

    # Show by task type
    for task_type in sorted(stats.keys()):
        task_stats = stats[task_type]
        abbr = task_type.split('_')[0]

        confirmed = task_stats['confirmed']
        flagged = task_stats['flagged']
        pending = task_stats['pending']
        total = task_stats['total']

        # Calculate target for A1/A2/A3
        if 'A1' in task_type:
            target = 50
            target_str = f" (target: {target})"
        elif 'A2' in task_type:
            target = 50
            target_str = f" (target: {target})"
        elif 'A3' in task_type:
            target = 30
            target_str = f" (target: {target})"
        else:
            target_str = ""

        print(f"\n{abbr}:{target_str}")
        print(f"  Confirmed: {confirmed:3d}")
        print(f"  Flagged:   {flagged:3d}")
        print(f"  Pending:   {pending:3d}")
        print(f"  Total:     {total:3d}")


def show_preview(qm: QueueManager, n: int = 20):
    """Show next N questions in queue."""
    qm.print_pending_queue(n)


def prioritize_task_type(qm: QueueManager, task_abbr: str):
    """
    Move pending/flagged questions of a task type to front.

    Args:
        qm: Queue manager
        task_abbr: Task type abbreviation (A1, A2, etc.)
    """
    if task_abbr not in TASK_TYPES:
        print(f"❌ Unknown task type: {task_abbr}")
        print(f"   Valid types: {', '.join(TASK_TYPES.keys())}")
        return

    task_type = TASK_TYPES[task_abbr]

    print(f"\nPrioritizing {task_abbr} questions...")
    print("=" * 70)

    # Move pending/flagged to front, confirmed to back
    qm.reorder_by_priority([
        {'task_types': [task_type], 'exclude_statuses': ['confirmed']},
        {'statuses': ['confirmed']}
    ])

    qm.save()
    print()
    qm.print_pending_queue(10)


def deprioritize_task_type(qm: QueueManager, task_abbr: str):
    """
    Move all questions of a task type to back.

    Args:
        qm: Queue manager
        task_abbr: Task type abbreviation (A1, A2, etc.)
    """
    if task_abbr not in TASK_TYPES:
        print(f"❌ Unknown task type: {task_abbr}")
        print(f"   Valid types: {', '.join(TASK_TYPES.keys())}")
        return

    task_type = TASK_TYPES[task_abbr]

    print(f"\nDeprioritizing {task_abbr} questions (moving to back)...")
    print("=" * 70)

    qm.move_to_back(task_types=[task_type])

    qm.save()
    print()
    qm.print_pending_queue(10)


def clear_task_type(qm: QueueManager, task_abbr: str):
    """
    Move all questions of a task type to back (alias for deprioritize).

    Args:
        qm: Queue manager
        task_abbr: Task type abbreviation (A1, A2, etc.)
    """
    deprioritize_task_type(qm, task_abbr)


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    # Initialize queue manager
    qm = QueueManager(
        questions_file="data/questions/all_questions_system.json",
        audit_state_file="data/audit_results/audit_state.json"
    )

    if command == "status":
        show_status(qm)

    elif command == "preview":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        show_preview(qm, n)

    elif command == "prioritize":
        if len(sys.argv) < 3:
            print("Usage: manage_queue.py prioritize <task_type>")
            print(f"Valid types: {', '.join(TASK_TYPES.keys())}")
            sys.exit(1)
        task_abbr = sys.argv[2].upper()
        prioritize_task_type(qm, task_abbr)

    elif command == "deprioritize" or command == "clear":
        if len(sys.argv) < 3:
            print("Usage: manage_queue.py deprioritize <task_type>")
            print(f"Valid types: {', '.join(TASK_TYPES.keys())}")
            sys.exit(1)
        task_abbr = sys.argv[2].upper()
        deprioritize_task_type(qm, task_abbr)

    else:
        print(f"❌ Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
