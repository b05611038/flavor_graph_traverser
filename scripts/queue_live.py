#!/usr/bin/env python3
"""
Manage the auditor queue in real-time without restarting.

Usage:
    python scripts/queue_live.py stats              # Show queue statistics
    python scripts/queue_live.py preview [N]        # Preview next N questions (default 20)
    python scripts/queue_live.py preview A2 [N]     # Preview next N A2 questions
    python scripts/queue_live.py prioritize A2      # Move A2 to front (not yet implemented)
"""

import sys
import requests
import json

AUDITOR_URL = "http://localhost:5000"


def show_stats():
    """Show queue statistics by task type."""
    response = requests.get(f"{AUDITOR_URL}/api/queue/stats")

    if response.status_code == 200:
        data = response.json()
        print("Queue Statistics by Task Type")
        print("=" * 70)
        print(f"{'Task Type':<35} {'Total':<8} {'Confirmed':<10} {'Flagged':<8} {'Pending':<8}")
        print("-" * 70)

        for task_type, stats in sorted(data['by_task_type'].items()):
            # Use short name
            short_name = task_type.split('_')[0]
            if task_type.startswith('A'):
                short_name = task_type[:2]

            print(f"{task_type:<35} {stats['total']:<8} {stats['confirmed']:<10} "
                  f"{stats['flagged']:<8} {stats['pending']:<8}")

        print("-" * 70)
        print(f"Total Pending: {data['total_pending']}")

    else:
        print(f"✗ HTTP Error {response.status_code}")


def preview_queue(task_type=None, limit=20):
    """Preview the next N questions in the queue."""
    params = {'limit': limit}
    if task_type:
        params['task_type'] = task_type

    response = requests.get(f"{AUDITOR_URL}/api/queue/preview", params=params)

    if response.status_code == 200:
        data = response.json()

        title = f"Next {limit} Questions in Queue"
        if task_type:
            title += f" (Task Type: {task_type})"
        print(title)
        print("=" * 70)
        print(f"Total Pending: {data['total_pending']}")
        print()

        for q in data['questions']:
            print(f"{q['position']:3}. [{q['task_type'][:2]}] {q['descriptor']}")
            print(f"     {q['text']}")
            print()

    else:
        print(f"✗ HTTP Error {response.status_code}")


def prioritize_task_type(task_type):
    """Prioritize a task type (move to front)."""
    response = requests.post(
        f"{AUDITOR_URL}/api/queue/prioritize",
        json={'task_type': task_type}
    )

    if response.status_code == 200:
        result = response.json()
        if result['success']:
            print(f"✓ {result['message']}")
        else:
            print(f"✗ {result.get('error', 'Unknown error')}")
    else:
        print(f"✗ HTTP Error {response.status_code}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == 'stats':
        show_stats()

    elif command == 'preview':
        task_type = None
        limit = 20

        # Parse arguments
        if len(sys.argv) > 2:
            # Check if arg is a task type or a number
            arg = sys.argv[2]
            if arg.isdigit():
                limit = int(arg)
            else:
                task_type = arg

        if len(sys.argv) > 3:
            limit = int(sys.argv[3])

        preview_queue(task_type, limit)

    elif command == 'prioritize':
        if len(sys.argv) < 3:
            print("Usage: python scripts/queue_live.py prioritize <task_type>")
            sys.exit(1)

        task_type = sys.argv[2]
        prioritize_task_type(task_type)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
