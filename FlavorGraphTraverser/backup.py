"""
Backup utility for critical data files.

Creates timestamped backups before any write operation.
Keeps the last N backups and prunes older ones automatically.
"""

import shutil
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("data/backups")
MAX_BACKUPS_PER_FILE = 20


def backup_before_write(file_path: Path | str, max_backups: int = MAX_BACKUPS_PER_FILE) -> Path | None:
    """
    Create a timestamped backup of file_path before overwriting it.

    Call this immediately before any write to a critical data file.
    Returns the backup path, or None if the source file doesn't exist yet.

    Automatically prunes old backups to keep at most max_backups copies.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
    backup_path = BACKUP_DIR / backup_name

    shutil.copy2(file_path, backup_path)
    logger.debug(f"Backup created: {backup_path}")

    _prune_old_backups(file_path.stem, file_path.suffix, max_backups)

    return backup_path


def _prune_old_backups(stem: str, suffix: str, max_backups: int) -> None:
    """Remove oldest backups beyond the max_backups limit (by modification time)."""
    pattern = f"{stem}_*{suffix}"
    backups = sorted(BACKUP_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    excess = len(backups) - max_backups
    for old in backups[:excess]:
        old.unlink()
        logger.debug(f"Pruned old backup: {old}")


def list_backups(file_path: Path | str) -> list[Path]:
    """Return all backups for a given file, newest first (by modification time)."""
    file_path = Path(file_path)
    pattern = f"{file_path.stem}_*{file_path.suffix}"
    return sorted(BACKUP_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
