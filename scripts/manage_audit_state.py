#!/usr/bin/env python3
"""
Audit State Management Tool

Provides utilities to check, validate, and manage audit state files.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
from datetime import datetime
from FlavorGraphTraverser.evaluation.audit_state_manager import (
    AuditStateManager,
    detect_state_files,
    CANONICAL_STATE_FILE,
    LEGACY_STATE_FILES
)


def cmd_status(args):
    """Show status of audit state files."""
    print("=" * 70)
    print("Audit State Status")
    print("=" * 70)

    # Detect all state files
    state_files = detect_state_files()

    if not state_files:
        print("\n❌ No state files found.")
        return

    print(f"\nFound {len(state_files)} state file(s):")
    print()

    for state_file in state_files:
        is_canonical = state_file == CANONICAL_STATE_FILE
        marker = "✓ CANONICAL" if is_canonical else "⚠️  LEGACY"

        # Load and show stats
        manager = AuditStateManager(state_file, read_only=True)
        stats = manager.get_stats()

        size = state_file.stat().st_size
        mtime = datetime.fromtimestamp(state_file.stat().st_mtime)

        print(f"{marker}  {state_file}")
        print(f"          Size: {size:,} bytes")
        print(f"          Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"          Confirmed: {stats['confirmed']}")
        print(f"          Flagged: {stats['flagged']}")
        print(f"          Total reviewed: {stats['total_reviewed']}")
        print()

    # Recommendations
    if len(state_files) > 1:
        print("⚠️  RECOMMENDATION:")
        print(f"   Multiple state files detected. Run migration to consolidate:")
        print(f"   python scripts/migrate_audit_state.py")
        print()


def cmd_validate(args):
    """Validate audit state file integrity."""
    state_file = Path(args.file) if args.file else CANONICAL_STATE_FILE

    print("=" * 70)
    print(f"Validating: {state_file}")
    print("=" * 70)

    if not state_file.exists():
        print(f"\n❌ File does not exist: {state_file}")
        return

    # Load and validate
    manager = AuditStateManager(state_file, read_only=True)
    errors = manager.validate_state()

    if not errors:
        stats = manager.get_stats()
        print(f"\n✅ State file is valid!")
        print(f"\n   Total reviewed: {stats['total_reviewed']}")
        print(f"   Confirmed: {stats['confirmed']}")
        print(f"   Flagged: {stats['flagged']}")
    else:
        print(f"\n❌ Found {len(errors)} validation error(s):")
        for error in errors:
            print(f"   - {error}")


def cmd_info(args):
    """Show detailed info about a specific question."""
    state_file = Path(args.file) if args.file else CANONICAL_STATE_FILE

    if not state_file.exists():
        print(f"❌ File does not exist: {state_file}")
        return

    manager = AuditStateManager(state_file, read_only=True)

    if args.question_id not in manager.states:
        print(f"❌ Question not found: {args.question_id}")
        print(f"   Status: pending (not reviewed yet)")
        return

    state = manager.states[args.question_id]

    print("=" * 70)
    print(f"Question: {state.question_id}")
    print("=" * 70)
    print(f"Status: {state.status}")
    print(f"Timestamp: {state.timestamp}")

    if state.notes:
        print(f"Notes: {state.notes}")

    if state.flag_reason:
        print(f"Flag Reason: {state.flag_reason}")


def cmd_summary(args):
    """Show summary statistics by task type."""
    state_file = Path(args.file) if args.file else CANONICAL_STATE_FILE

    if not state_file.exists():
        print(f"❌ File does not exist: {state_file}")
        return

    manager = AuditStateManager(state_file, read_only=True)
    stats = manager.get_stats()

    print("=" * 70)
    print("Audit Summary")
    print("=" * 70)
    print(f"\nTotal reviewed: {stats['total_reviewed']}")
    print(f"Confirmed: {stats['confirmed']}")
    print(f"Flagged: {stats['flagged']}")

    # Group by task type (extract from question IDs)
    by_task_type = {}
    for qid, state in manager.states.items():
        # Extract task type from ID (e.g., "A1_root_classification_001" -> "A1_root_classification")
        parts = qid.split('_')
        if len(parts) >= 3:
            task_type = '_'.join(parts[:3])
        else:
            task_type = "unknown"

        if task_type not in by_task_type:
            by_task_type[task_type] = {"confirmed": 0, "flagged": 0}

        if state.status == "confirmed":
            by_task_type[task_type]["confirmed"] += 1
        elif state.status == "flagged":
            by_task_type[task_type]["flagged"] += 1

    if by_task_type:
        print("\nBy Task Type:")
        for task_type in sorted(by_task_type.keys()):
            counts = by_task_type[task_type]
            total = counts["confirmed"] + counts["flagged"]
            print(f"  {task_type}:")
            print(f"    Total: {total}")
            print(f"    Confirmed: {counts['confirmed']}")
            print(f"    Flagged: {counts['flagged']}")


def main():
    parser = argparse.ArgumentParser(
        description="Audit State Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # status command
    subparsers.add_parser(
        'status',
        help='Show status of all audit state files'
    )

    # validate command
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate audit state file integrity'
    )
    validate_parser.add_argument(
        '--file',
        help='State file to validate (default: canonical location)'
    )

    # info command
    info_parser = subparsers.add_parser(
        'info',
        help='Show info about a specific question'
    )
    info_parser.add_argument(
        'question_id',
        help='Question ID to look up'
    )
    info_parser.add_argument(
        '--file',
        help='State file to search (default: canonical location)'
    )

    # summary command
    summary_parser = subparsers.add_parser(
        'summary',
        help='Show summary statistics'
    )
    summary_parser.add_argument(
        '--file',
        help='State file to summarize (default: canonical location)'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Dispatch to command handler
    if args.command == 'status':
        cmd_status(args)
    elif args.command == 'validate':
        cmd_validate(args)
    elif args.command == 'info':
        cmd_info(args)
    elif args.command == 'summary':
        cmd_summary(args)


if __name__ == '__main__':
    main()
