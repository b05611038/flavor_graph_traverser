# Backup System Usage

## Overview

**Version-numbered backups** where the number = **confirmed question count**
- Current state: `data/questions/all_questions_system.json` (98 confirmed)
- Backups: `data/backups/backup_98.json`, `backup_100.json`, etc.
- Each backup includes metadata header showing confirmed and total counts

## Commands

### Create Backup (if needed)
```bash
python scripts/backup_manager.py backup
```
- Creates backup only if none exists for today
- Filename = `backup_N.json` where N = **confirmed question count**
- Also backs up audit state as `audit_state_N.json`

### List All Backups
```bash
python scripts/backup_manager.py list
```
Output:
```
Available Backups:
======================================================================
Version      Date         A1     A2     A3     Total
----------------------------------------------------------------------
backup_98    2026-02-09   48     32     18     443
backup_90    2026-02-08   45     28     17     410
...
```

**Note:** Version number (98) = confirmed questions (48+32+18), not total questions (443)

### Restore from Backup
```bash
python scripts/backup_manager.py restore 98
```
- Restores questions and audit state to version 98 (98 confirmed questions)
- Creates backup of current state first (safe to undo)

## Automatic Backups

### In Python Scripts
```python
# Add to the top of any script that modifies questions
from scripts.backup_manager import create_backup_if_needed

# At the start of main()
def main():
    # This creates backup automatically (once per day)
    create_backup_if_needed()

    # ... rest of your script ...
```

### When Adding Questions
```python
# Example: Adding new A2 questions
from scripts.backup_manager import create_backup_if_needed

create_backup_if_needed()  # Creates backup_98.json (48+32+18 confirmed)

# Generate and confirm 2 new A2 questions
# Now have 100 confirmed (48+34+18)

# Next day, first modification will create backup_100.json
```

## Backup Metadata

Each backup includes a metadata header:

```json
{
  "metadata": {
    "total_questions": 443,          ← All questions (including pending/flagged)
    "last_modified": "2026-02-09T16:22:28",
    "by_category": {
      "A": 320,
      "E": 113,
      "F": 10
    },
    "by_task_type": {
      "A1_root_classification": 121,
      "A2_ancestor_verification": 85,
      "A3_sibling_identification": 72,
      ...
    },
    "confirmed_counts": {            ← Version number = sum of these
      "A1": 48,
      "A2": 32,
      "A3": 18                       ← 48+32+18 = 98 = backup_98.json
    }
  },
  "questions": [ ... ]
}
```

## How It Works

1. **Once per day**: First modification of the day triggers backup
2. **Version number**: Backup number = current question count
3. **Metadata**: Each backup has header showing state at that version
4. **Safe**: Restore always backs up current state first

## Benefits

✓ **Progress tracking**: Version number = confirmed questions (your actual progress!)
✓ **Simple**: Just one backup per day, named by confirmed count
✓ **Safe**: Can always restore previous state
✓ **Fast**: List backups shows key metrics at a glance
✓ **Automatic**: Scripts call `create_backup_if_needed()` once

## Example Workflow

### Day 1: Audit A3 questions
```bash
# Start auditing (backup created automatically)
python scripts/audit_questions_web.py

# Confirm 5 A3 questions during audit
# (no new backup - same day, same question count)
```

### Day 2: Add 18 new A2 questions
```bash
# Generate questions (creates backup_98.json first)
python scripts/generate_a2_questions.py

# Confirm all 18 during audit
# Now have 116 confirmed (48+50+18)
# Next modification tomorrow will create backup_116.json
```

### Day 3: Realized mistake - restore
```bash
# List backups to find version
python scripts/backup_manager.py list

# Restore to before adding A2s
python scripts/backup_manager.py restore 98

# Back to 98 confirmed questions!
```

## Migration from Old Backups

Your old timestamped backups are still available:
```
data/questions/all_questions_system.json.backup_20260209_143930
data/audit_results/audit_state.json.backup_20260209_145507
```

These are kept for reference but the new system uses version numbers.

---

**Current Status:**
- ✅ Initial backup created: `backup_98.json`
- ✅ Shows: 98 confirmed (48 A1, 32 A2, 18 A3), 443 total questions
- ✅ Next backup will be `backup_N.json` where N = confirmed count after changes
