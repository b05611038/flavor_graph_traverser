"""
Unified Audit State Manager

Provides thread-safe, single-source-of-truth state management for question auditing.
Prevents data loss and conflicts between multiple interfaces.
"""

import json
import fcntl
import os
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import shutil


# Canonical state file location
CANONICAL_STATE_FILE = Path("data/audit_results/audit_state.json")
LEGACY_STATE_FILES = [
    Path("data/audit_state.json"),
    Path("data/audit_results/audit_state_20260203.json"),
]


@dataclass
class QuestionAuditState:
    """State of a question in the audit process."""
    question_id: str
    status: str  # "pending", "confirmed", "flagged"
    timestamp: str
    notes: Optional[str] = None
    flag_reason: Optional[str] = None


class AuditStateManager:
    """
    Thread-safe state manager with file locking.

    Features:
    - Single canonical state file location
    - Atomic writes with file locking
    - Automatic backup before writes
    - State validation
    - Migration from legacy files
    """

    def __init__(self, state_file: Optional[Path] = None, read_only: bool = False):
        """
        Initialize state manager.

        Args:
            state_file: Path to state file (defaults to canonical location)
            read_only: If True, prevents any writes to state file
        """
        self.state_file = Path(state_file) if state_file else CANONICAL_STATE_FILE
        self.read_only = read_only
        self.states: Dict[str, QuestionAuditState] = {}

        # Ensure parent directory exists
        if not read_only:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Check for legacy files and warn
        self._check_legacy_files()

        # Load state
        self.load_state()

    def _check_legacy_files(self):
        """Check for legacy state files and warn user."""
        found_legacy = []
        for legacy_file in LEGACY_STATE_FILES:
            if legacy_file.exists() and legacy_file != self.state_file:
                found_legacy.append(legacy_file)

        if found_legacy:
            print(f"\n⚠️  WARNING: Found legacy state files:")
            for f in found_legacy:
                print(f"    {f}")
            print(f"\n   Current canonical file: {self.state_file}")
            print(f"   Run 'python scripts/migrate_audit_state.py' to consolidate.\n")

    def load_state(self):
        """Load state from file with read lock."""
        if not self.state_file.exists():
            self.states = {}
            return

        with open(self.state_file, 'r') as f:
            # Acquire shared lock for reading
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
                self.states = {
                    qid: QuestionAuditState(**state_dict)
                    for qid, state_dict in data.items()
                }
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def save_state(self):
        """Save state to file with exclusive lock and atomic write."""
        if self.read_only:
            raise PermissionError(
                "Cannot save state in read-only mode. "
                "This interface is read-only to prevent conflicts."
            )

        # Create backup
        if self.state_file.exists():
            backup_file = self.state_file.with_suffix('.json.backup')
            shutil.copy2(self.state_file, backup_file)

        # Atomic write: write to temp file first
        temp_file = self.state_file.with_suffix('.json.tmp')

        with open(temp_file, 'w') as f:
            # Acquire exclusive lock for writing
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                data = {qid: asdict(state) for qid, state in self.states.items()}
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        # Atomic rename
        temp_file.rename(self.state_file)

    def reload_state(self):
        """Reload state from file (useful for read-only interfaces)."""
        self.load_state()

    def get_status(self, question_id: str) -> str:
        """Get status of a question."""
        if question_id in self.states:
            return self.states[question_id].status
        return "pending"

    def confirm_question(self, question_id: str, notes: Optional[str] = None):
        """Mark question as confirmed."""
        if self.read_only:
            raise PermissionError("Cannot modify state in read-only mode")

        self.states[question_id] = QuestionAuditState(
            question_id=question_id,
            status="confirmed",
            timestamp=datetime.now().isoformat(),
            notes=notes
        )
        self.save_state()

    def flag_question(self, question_id: str, reason: str, notes: Optional[str] = None):
        """Mark question as flagged."""
        if self.read_only:
            raise PermissionError("Cannot modify state in read-only mode")

        self.states[question_id] = QuestionAuditState(
            question_id=question_id,
            status="flagged",
            timestamp=datetime.now().isoformat(),
            flag_reason=reason,
            notes=notes
        )
        self.save_state()

    def unflag_question(self, question_id: str):
        """Remove flag from question (back to pending)."""
        if self.read_only:
            raise PermissionError("Cannot modify state in read-only mode")

        if question_id in self.states:
            del self.states[question_id]
            self.save_state()

    def get_confirmed_questions(self) -> List[str]:
        """Get list of confirmed question IDs."""
        return [qid for qid, state in self.states.items() if state.status == "confirmed"]

    def get_flagged_questions(self) -> List[str]:
        """Get list of flagged question IDs."""
        return [qid for qid, state in self.states.items() if state.status == "flagged"]

    def get_pending_questions(self, all_question_ids: List[str]) -> List[str]:
        """Get list of pending question IDs."""
        return [qid for qid in all_question_ids if self.get_status(qid) == "pending"]

    def get_stats(self) -> Dict[str, int]:
        """Get audit statistics."""
        return {
            "confirmed": len([s for s in self.states.values() if s.status == "confirmed"]),
            "flagged": len([s for s in self.states.values() if s.status == "flagged"]),
            "total_reviewed": len(self.states)
        }

    def validate_state(self) -> List[str]:
        """
        Validate state integrity.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        for qid, state in self.states.items():
            # Check required fields
            if not state.question_id:
                errors.append(f"Missing question_id for state: {qid}")

            if state.question_id != qid:
                errors.append(f"Mismatched question_id: {qid} != {state.question_id}")

            # Check status values
            if state.status not in ["pending", "confirmed", "flagged"]:
                errors.append(f"Invalid status for {qid}: {state.status}")

            # Check flagged questions have reasons
            if state.status == "flagged" and not state.flag_reason:
                errors.append(f"Flagged question {qid} missing flag_reason")

        return errors


def detect_state_files() -> List[Path]:
    """
    Detect all audit state files in the project.

    Returns:
        List of paths to state files found
    """
    state_files = []

    # Check canonical location
    if CANONICAL_STATE_FILE.exists():
        state_files.append(CANONICAL_STATE_FILE)

    # Check legacy locations
    for legacy_file in LEGACY_STATE_FILES:
        if legacy_file.exists():
            state_files.append(legacy_file)

    return state_files


def merge_state_files(source_files: List[Path], target_file: Path) -> Dict[str, int]:
    """
    Merge multiple state files into a single canonical file.

    Conflict resolution: most recent timestamp wins.

    Args:
        source_files: List of state files to merge
        target_file: Destination file

    Returns:
        Statistics about the merge
    """
    merged_states = {}
    stats = {
        "total_files": len(source_files),
        "total_states": 0,
        "conflicts_resolved": 0,
        "confirmed": 0,
        "flagged": 0
    }

    # Load all states
    for source_file in source_files:
        if not source_file.exists():
            continue

        with open(source_file, 'r') as f:
            data = json.load(f)

        for qid, state_dict in data.items():
            stats["total_states"] += 1

            # Check for conflicts
            if qid in merged_states:
                stats["conflicts_resolved"] += 1
                # Keep most recent
                existing_time = datetime.fromisoformat(merged_states[qid]["timestamp"])
                new_time = datetime.fromisoformat(state_dict["timestamp"])
                if new_time <= existing_time:
                    continue  # Keep existing

            merged_states[qid] = state_dict

    # Count final stats
    for state in merged_states.values():
        if state["status"] == "confirmed":
            stats["confirmed"] += 1
        elif state["status"] == "flagged":
            stats["flagged"] += 1

    # Write merged state
    target_file.parent.mkdir(parents=True, exist_ok=True)
    with open(target_file, 'w') as f:
        json.dump(merged_states, f, indent=2)

    return stats
