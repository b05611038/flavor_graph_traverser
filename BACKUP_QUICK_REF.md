# Backup System - Quick Reference

## ✅ Your Backup Strategy is Now Active!

### Current State
```
data/backups/backup_98.json  ← 98 confirmed (48 A1 + 32 A2 + 18 A3)
```

### How It Works

**Version-numbered backups** where number = **confirmed question count**:
- `backup_98.json` = backup when you had 98 confirmed questions
- `backup_116.json` = backup when you had 116 confirmed questions (98 + 18 more)
- etc.

**One backup per day:**
- First modification of the day → creates backup
- Rest of the day → no duplicate backups
- Tomorrow → new backup if you modify files

**Each backup includes header:**
```json
{
  "metadata": {
    "total_questions": 443,        ← All questions (including pending)
    "confirmed_counts": {           ← Only counts confirmed
      "A1": 48,
      "A2": 32,
      "A3": 18
    }
  }
}
```

---

## Quick Commands

```bash
# List all backups (shows A1/A2/A3 confirmed counts)
python scripts/backup_manager.py list

# Create backup manually (if needed)
python scripts/backup_manager.py backup

# Restore to specific confirmed count
python scripts/backup_manager.py restore 98
```

---

## For Script Developers

Add this to any script that modifies questions:

```python
from scripts.backup_manager import create_backup_if_needed

def main():
    create_backup_if_needed()  # Auto-backup (once per day)

    # ... your modifications ...
```

---

## Benefits

✓ **Simple**: One command to backup, list, or restore
✓ **Automatic**: Scripts auto-backup before changes
✓ **Progress tracking**: Version number = confirmed questions (your actual progress!)
✓ **Safe**: Always backup before restore
✓ **Fast**: See confirmed counts without opening files

---

## Example Timeline

```
backup_98.json   → 48 A1, 32 A2, 18 A3  (today)
backup_100.json  → 50 A1, 32 A2, 18 A3  (after completing A1)
backup_118.json  → 50 A1, 50 A2, 18 A3  (after completing A2)
backup_148.json  → 50 A1, 50 A2, 30 A3, 18 A4  (after completing A3 + starting A4)
```

---

**Status: ✅ Active**
**Initial Backup: backup_98.json** (2026-02-09)
**Next Backup: backup_N.json** (when confirmed count changes tomorrow)
