"""
Version-numbered backup manager.

Strategy:
- Backup filename = backup_N.json where N = total question count
- Only create one backup per day (check if today's backup exists)
- Add header with metadata showing counts by category
- Automatically called before any modification

Usage:
    from scripts.backup_manager import create_backup_if_needed

    create_backup_if_needed()  # Creates backup if needed
    # ... then modify files ...
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from collections import defaultdict


def get_question_stats(questions_data):
    """Get statistics about questions."""
    questions = questions_data.get('questions', [])

    stats = {
        'total_count': len(questions),
        'by_category': defaultdict(int),
        'by_task_type': defaultdict(int),
        'timestamp': datetime.now().isoformat()
    }

    # Count by category and task type
    for q in questions:
        category = q.get('category', 'UNKNOWN')
        task_type = q.get('task_type', 'UNKNOWN')
        stats['by_category'][category] += 1
        stats['by_task_type'][task_type] += 1

    return stats


def get_confirmed_stats(questions_data, audit_state):
    """Get statistics about confirmed questions that actually exist."""
    confirmed_by_task = defaultdict(int)

    # Get set of confirmed IDs
    confirmed_ids = {qid for qid, state in audit_state.items()
                     if isinstance(state, dict) and state.get('status') == 'confirmed'}

    # Count only questions that exist in questions file
    for q in questions_data.get('questions', []):
        if q['id'] in confirmed_ids:
            task_type = q.get('task_type', '').split('_')[0]
            confirmed_by_task[task_type] += 1

    return dict(confirmed_by_task)


def add_metadata_header(questions_data, audit_state):
    """Add metadata header to questions data."""
    stats = get_question_stats(questions_data)
    confirmed_stats = get_confirmed_stats(questions_data, audit_state)

    metadata = {
        'total_questions': stats['total_count'],
        'last_modified': stats['timestamp'],
        'by_category': dict(stats['by_category']),
        'by_task_type': dict(stats['by_task_type']),
        'confirmed_counts': confirmed_stats
    }

    questions_data['metadata'] = metadata
    return questions_data


def get_latest_backup_date(backup_dir):
    """Get the date of the most recent backup."""
    backup_files = list(backup_dir.glob('backup_*.json'))
    if not backup_files:
        return None

    # Get most recent backup
    latest = max(backup_files, key=lambda p: p.stat().st_mtime)
    latest_date = datetime.fromtimestamp(latest.stat().st_mtime).date()
    return latest_date


def get_latest_backup_version(backup_dir):
    """Get the version number of the most recent backup."""
    backup_files = list(backup_dir.glob('backup_*.json'))
    if not backup_files:
        return None

    versions = []
    for f in backup_files:
        try:
            version = int(f.stem.split('_')[1])
            versions.append(version)
        except:
            continue

    return max(versions) if versions else None


def create_backup_if_needed(force=False, incremental=True):
    """
    Create a version-numbered backup if needed.

    Strategy:
    1. Daily backup: Create backup if none exists today (safety net)
    2. Incremental backup: Create backup if confirmed count changed

    Args:
        force: If True, create backup regardless of checks
        incremental: If True, create backup when confirmed count changes

    Returns:
        Path to backup file if created, None otherwise
    """
    questions_path = Path('data/questions/all_questions_system.json')
    audit_path = Path('data/audit_results/audit_state.json')
    backup_dir = Path('data/backups')

    # Create backup directory if needed
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Load current data
    with open(questions_path) as f:
        questions_data = json.load(f)

    with open(audit_path) as f:
        audit_state = json.load(f)

    # Add metadata header first to get confirmed count
    backup_data = add_metadata_header(questions_data.copy(), audit_state)

    # Get confirmed count for version number
    confirmed_counts = backup_data['metadata']['confirmed_counts']
    confirmed_total = sum(confirmed_counts.values())

    # Check if we need to create backup
    if not force:
        # Check 1: Do we have a backup from today? (Daily backup)
        today = datetime.now().date()
        has_backup_today = False
        backup_files = list(backup_dir.glob('backup_*.json'))

        for backup_file in backup_files:
            backup_date = datetime.fromtimestamp(backup_file.stat().st_mtime).date()
            if backup_date == today:
                has_backup_today = True
                break

        # Check 2: Has confirmed count changed? (Incremental backup)
        latest_version = get_latest_backup_version(backup_dir)
        count_changed = latest_version is not None and latest_version != confirmed_total

        # Decide whether to backup
        if has_backup_today and not (incremental and count_changed):
            if count_changed:
                print(f"Confirmed count changed ({latest_version} → {confirmed_total}) but backup exists for today")
                print(f"To force incremental backup, run: python scripts/backup_manager.py backup")
            else:
                print(f"Backup already exists for today with same confirmed count ({confirmed_total})")
            return None

        # Print reason for backup
        if not has_backup_today:
            print(f"Creating daily backup (first backup of the day)...")
        elif count_changed:
            print(f"Creating incremental backup (confirmed count: {latest_version} → {confirmed_total})...")

    # Create backup filename with CONFIRMED count
    backup_name = f"backup_{confirmed_total}.json"
    backup_path = backup_dir / backup_name

    # Save backup
    with open(backup_path, 'w') as f:
        json.dump(backup_data, f, indent=2)

    # Also backup audit state with same version number
    audit_backup_path = backup_dir / f"audit_state_{confirmed_total}.json"
    with open(audit_backup_path, 'w') as f:
        json.dump(audit_state, f, indent=2)

    print(f"✓ Created backup: {backup_name}")
    print(f"  Confirmed questions: {confirmed_total}")

    # Print summary
    metadata = backup_data['metadata']
    confirmed = metadata.get('confirmed_counts', {})

    print(f"  Confirmed: A1={confirmed.get('A1', 0)}, "
          f"A2={confirmed.get('A2', 0)}, "
          f"A3={confirmed.get('A3', 0)}")

    return backup_path


def list_backups():
    """List all backups with metadata."""
    backup_dir = Path('data/backups')

    if not backup_dir.exists():
        print("No backups directory found")
        return

    backup_files = sorted(backup_dir.glob('backup_*.json'),
                         key=lambda p: int(p.stem.split('_')[1]),
                         reverse=True)

    if not backup_files:
        print("No backups found")
        return

    print("\nAvailable Backups:")
    print("="*70)
    print(f"{'Version':<12} {'Date':<12} {'A1':<6} {'A2':<6} {'A3':<6} {'Total'}")
    print("-"*70)

    for backup_file in backup_files[:10]:  # Show last 10
        try:
            with open(backup_file) as f:
                data = json.load(f)

            metadata = data.get('metadata', {})
            version = int(backup_file.stem.split('_')[1])
            modified_date = datetime.fromisoformat(metadata.get('last_modified', ''))
            date_str = modified_date.strftime('%Y-%m-%d')

            confirmed = metadata.get('confirmed_counts', {})
            a1 = confirmed.get('A1', 0)
            a2 = confirmed.get('A2', 0)
            a3 = confirmed.get('A3', 0)
            total = metadata.get('total_questions', 0)

            print(f"backup_{version:<5} {date_str:<12} {a1:<6} {a2:<6} {a3:<6} {total}")

        except Exception as e:
            print(f"{backup_file.name}: Error reading - {e}")

    if len(backup_files) > 10:
        print(f"\n... and {len(backup_files)-10} more backups")


def restore_from_backup(version_number):
    """
    Restore from a specific backup version.

    Args:
        version_number: The version number to restore (e.g., 443)
    """
    backup_dir = Path('data/backups')
    backup_path = backup_dir / f"backup_{version_number}.json"
    audit_backup_path = backup_dir / f"audit_state_{version_number}.json"

    if not backup_path.exists():
        print(f"Error: Backup version {version_number} not found")
        return False

    # Confirm with user
    print(f"This will restore questions to version {version_number}")
    print("Current files will be backed up first")

    # Create backup of current state first
    create_backup_if_needed(force=True)

    # Restore questions
    questions_path = Path('data/questions/all_questions_system.json')
    shutil.copy(backup_path, questions_path)
    print(f"✓ Restored questions from backup_{version_number}")

    # Restore audit state if exists
    if audit_backup_path.exists():
        audit_path = Path('data/audit_results/audit_state.json')
        shutil.copy(audit_backup_path, audit_path)
        print(f"✓ Restored audit state from audit_state_{version_number}")

    return True


def create_incremental_backup():
    """
    Force create an incremental backup (used after confirming questions).

    This is useful to call after confirming questions in the audit interface
    to capture progress immediately.
    """
    return create_backup_if_needed(force=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "backup":
            # Check for --force flag
            force = "--force" in sys.argv
            create_backup_if_needed(force=force)

        elif command == "incremental":
            # Force incremental backup (used after confirming questions)
            create_incremental_backup()

        elif command == "list":
            list_backups()

        elif command == "restore":
            if len(sys.argv) < 3:
                print("Usage: python backup_manager.py restore <version_number>")
            else:
                version = int(sys.argv[2])
                restore_from_backup(version)

        else:
            print("Unknown command. Usage:")
            print("  python backup_manager.py backup            # Create backup if needed (daily)")
            print("  python backup_manager.py backup --force    # Force create backup")
            print("  python backup_manager.py incremental       # Force incremental backup")
            print("  python backup_manager.py list              # List all backups")
            print("  python backup_manager.py restore N         # Restore from version N")

    else:
        # Default: create backup if needed
        create_backup_if_needed()
