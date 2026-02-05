# Audit State Management System

## Overview

The audit state management system has been redesigned to provide a safe, single-source-of-truth architecture that prevents data loss and confusion.

## Key Features

### 1. Single Canonical State File

**Location:** `data/audit_results/audit_state.json`

All audit state is now stored in one canonical location. This eliminates:
- Data divergence between multiple files
- Confusion about which file is current
- Risk of losing audit progress

### 2. Thread-Safe Operations

- **File locking:** Prevents corruption from concurrent access
- **Atomic writes:** Uses temp files and atomic rename
- **Automatic backups:** Creates `.backup` before each write

### 3. Read-Only Review Interface

The review interface (`review_audited_questions.py`) runs in read-only mode by default:
- Cannot accidentally modify state
- Auto-reloads to show changes from auditor
- Safe for viewing while auditing

### 4. State Validation

Built-in validation checks:
- Required fields present
- Status values valid
- Flagged questions have reasons
- No mismatched IDs

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Canonical State File                     │
│         data/audit_results/audit_state.json             │
└─────────────────┬───────────────────────────────────────┘
                  │
       ┌──────────┴──────────┐
       │                     │
       ▼                     ▼
┌─────────────┐       ┌─────────────┐
│  Auditor    │       │   Review    │
│  (Port 5000)│       │ (Port 5001) │
│             │       │             │
│ READ/WRITE  │       │  READ-ONLY  │
│             │       │ Auto-reload │
└─────────────┘       └─────────────┘
```

## Quick Start

### 1. Start Auditing

```bash
# Start auditor (read/write)
python scripts/audit_questions_web.py data/questions/all_questions_system.json --port 5000
```

Opens at: http://localhost:5000
- Confirm/Flag/Skip questions
- Changes saved to canonical state file

### 2. View Progress

```bash
# Start review interface (read-only)
python scripts/review_audited_questions.py data/questions/all_questions_system.json --port 5001
```

Opens at: http://localhost:5001
- View all confirmed/flagged questions
- Auto-reloads when auditor makes changes
- Safe to keep open while auditing

### 3. Check Status

```bash
# Show status of all state files
python scripts/manage_audit_state.py status
```

### 4. Validate State

```bash
# Check state file integrity
python scripts/manage_audit_state.py validate
```

### 5. View Summary

```bash
# Show statistics by task type
python scripts/manage_audit_state.py summary
```

## Migration

If you have legacy state files, consolidate them:

```bash
# Merge all state files into canonical location
python scripts/migrate_audit_state.py

# With dry-run to see what would happen
python scripts/migrate_audit_state.py --dry-run
```

Migration features:
- Merges multiple state files
- Resolves conflicts (keeps most recent timestamp)
- Backs up legacy files (adds `.migrated` suffix)
- Safe: validates before proceeding

## File Locking

The system uses `fcntl` for thread-safe file access:

- **Reading:** Shared lock (multiple readers OK)
- **Writing:** Exclusive lock (blocks all other access)
- **Atomic writes:** Write to temp file, then atomic rename

This prevents:
- Corruption from concurrent writes
- Partial reads during writes
- Data loss from interrupted operations

## State File Format

```json
{
  "question_id": {
    "question_id": "A1_root_classification_001",
    "status": "confirmed",  // "pending" | "confirmed" | "flagged"
    "timestamp": "2026-02-05T10:35:53.123456",
    "notes": "Optional notes",
    "flag_reason": "Required for flagged questions"
  }
}
```

## Best Practices

### Do's

✅ Use auditor (port 5000) for making changes
✅ Keep review interface (port 5001) open to monitor progress
✅ Run `status` command to check for issues
✅ Run `validate` command periodically
✅ Let migration tool handle consolidation

### Don'ts

❌ Don't manually edit state files
❌ Don't create multiple state files
❌ Don't use `--read-write` on review interface
❌ Don't delete canonical state file
❌ Don't disable file locking

## Troubleshooting

### Multiple State Files Detected

**Problem:** Migration tool shows multiple state files

**Solution:**
```bash
python scripts/migrate_audit_state.py
```

### State Validation Errors

**Problem:** `validate` command shows errors

**Solution:**
1. Review error messages
2. If corrupted, restore from `.backup` file
3. If conflicts, run migration again

### Permission Errors in Review Interface

**Problem:** "Cannot save state in read-only mode"

**Cause:** Review interface is read-only by default (this is correct!)

**Solution:** Use auditor (port 5000) to make changes instead

### Outdated Data in Review Interface

**Problem:** Review interface not showing latest changes

**Cause:** Auto-reload happens on API calls only

**Solution:** Refresh the page or wait for next auto-refresh (10 seconds)

## Advanced Usage

### Custom State File Location

```bash
# Use non-canonical location (not recommended)
python scripts/audit_questions_web.py questions.json --state-file /custom/path/state.json
```

### Enable Write Access on Review Interface

```bash
# NOT RECOMMENDED - use auditor instead
python scripts/review_audited_questions.py questions.json --read-write
```

### Query Specific Question

```bash
# Show info about a question
python scripts/manage_audit_state.py info A1_root_classification_001
```

## Technical Details

### AuditStateManager Class

Core state management with:
- File locking (shared for read, exclusive for write)
- Atomic writes with temp files
- Automatic backups
- State validation
- Legacy file detection

### QuestionAuditor Wrapper

Backwards-compatible wrapper around `AuditStateManager`:
- Maintains old API
- Delegates to new state manager
- Exposes read-only flag

### Canonical Location

Default: `data/audit_results/audit_state.json`

Defined in: `FlavorGraphTraverser/evaluation/audit_state_manager.py`

```python
CANONICAL_STATE_FILE = Path("data/audit_results/audit_state.json")
```

## Migration Statistics

After running migration, you'll see:
- Files merged
- Total states processed
- Conflicts resolved (same question in multiple files)
- Final confirmed/flagged counts

Conflicts are resolved by keeping the state with the most recent timestamp.

## Security

- File permissions inherited from parent directory
- No network access required
- All operations are local filesystem
- Backups prevent accidental data loss

## Performance

- File locking adds minimal overhead (~1ms per operation)
- Atomic writes ensure no partial state
- Read-only interface can scale to multiple viewers
- State file size grows linearly with reviewed questions

## Future Improvements

Potential enhancements:
- Watch file for changes (inotify/FSEvents)
- Real-time updates via WebSockets
- Export to SQLite for complex queries
- Undo/redo functionality
- Audit trail with full history

---

Last Updated: 2026-02-05
Version: 2.0
