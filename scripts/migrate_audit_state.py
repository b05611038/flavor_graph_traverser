#!/usr/bin/env python3
"""
Migrate and consolidate audit state files.

Merges all legacy state files into the canonical location.
Resolves conflicts by keeping the most recent state.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from datetime import datetime
from FlavorGraphTraverser.evaluation.audit_state_manager import (
    detect_state_files,
    merge_state_files,
    CANONICAL_STATE_FILE,
    LEGACY_STATE_FILES
)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate and consolidate audit state files"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        '--backup',
        action='store_true',
        default=True,
        help="Create backup of legacy files before migration (default: True)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Audit State Migration Tool")
    print("=" * 70)

    # Detect all state files
    print("\n1. Detecting state files...")
    state_files = detect_state_files()

    if not state_files:
        print("   No state files found.")
        return

    print(f"   Found {len(state_files)} state file(s):")
    for f in state_files:
        size = f.stat().st_size if f.exists() else 0
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        is_canonical = " (CANONICAL)" if f == CANONICAL_STATE_FILE else ""
        print(f"      {f} ({size} bytes, modified {mtime}){is_canonical}")

    # Check if migration is needed
    if len(state_files) == 1 and state_files[0] == CANONICAL_STATE_FILE:
        print("\n✅ Already using canonical state file. No migration needed.")
        return

    # Plan migration
    print(f"\n2. Planning migration...")
    print(f"   Target: {CANONICAL_STATE_FILE}")

    if args.dry_run:
        print("\n   [DRY RUN] Would merge the following files:")
        for f in state_files:
            print(f"      {f}")
        print("\n   Run without --dry-run to perform migration.")
        return

    # Confirm with user
    print("\n   This will:")
    print(f"      - Merge all state files into: {CANONICAL_STATE_FILE}")
    if args.backup:
        print(f"      - Backup legacy files (add .migrated suffix)")
    else:
        print(f"      - DELETE legacy files")
    print(f"      - Resolve conflicts (keep most recent timestamp)")

    response = input("\n   Continue? [y/N]: ")
    if response.lower() != 'y':
        print("   Migration cancelled.")
        return

    # Perform migration
    print("\n3. Merging state files...")
    stats = merge_state_files(state_files, CANONICAL_STATE_FILE)

    print(f"\n   Merge complete:")
    print(f"      Files merged: {stats['total_files']}")
    print(f"      Total states processed: {stats['total_states']}")
    print(f"      Conflicts resolved: {stats['conflicts_resolved']}")
    print(f"      Final confirmed: {stats['confirmed']}")
    print(f"      Final flagged: {stats['flagged']}")

    # Handle legacy files
    print("\n4. Cleaning up legacy files...")
    for legacy_file in state_files:
        if legacy_file == CANONICAL_STATE_FILE:
            continue

        if args.backup:
            backup_file = legacy_file.with_suffix('.json.migrated')
            legacy_file.rename(backup_file)
            print(f"      Backed up: {legacy_file} -> {backup_file}")
        else:
            legacy_file.unlink()
            print(f"      Deleted: {legacy_file}")

    print("\n" + "=" * 70)
    print("✅ Migration complete!")
    print(f"   Canonical state file: {CANONICAL_STATE_FILE}")
    print("=" * 70)


if __name__ == '__main__':
    main()
