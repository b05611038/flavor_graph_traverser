# Backup System: Daily + Incremental

## ✅ You Now Have BOTH Backup Mechanisms!

### Two-Level Backup Strategy

**1. Daily Backup (Safety Net)**
- Creates backup on first modification of the day
- Automatic safety net before you start working
- One backup per day minimum

**2. Incremental Backup (Progress Tracking)**
- Creates backup whenever confirmed count changes
- Captures every milestone (every time you confirm questions)
- Fine-grained restoration points

---

## How It Works

### Morning: Daily Backup (Automatic)

```bash
# You start working (generate questions, audit, etc.)
python scripts/generate_a2_questions.py
# → Automatically creates backup_98.json (daily backup)

# Or start audit interface
python scripts/audit_questions_web.py
# → Automatically creates backup_98.json if not exists today
```

### During Day: Incremental Backups (On Demand)

```bash
# After confirming some questions in audit interface
# Manually create incremental backup
python scripts/backup_manager.py incremental

# Or call from Python:
from scripts.backup_manager import create_incremental_backup
create_incremental_backup()  # Creates backup_100.json, backup_103.json, etc.
```

---

## Example Timeline

### Day 1 (2026-02-09)

**9:00 AM - Start auditing**
```bash
python scripts/audit_questions_web.py
```
→ Creates `backup_98.json` (48 A1, 32 A2, 18 A3) - **Daily backup**

**11:00 AM - Confirmed 2 A1 questions**
```bash
# In audit interface, click "Confirm" on 2 questions
# Then create incremental backup:
python scripts/backup_manager.py incremental
```
→ Creates `backup_100.json` (50 A1, 32 A2, 18 A3) - **Incremental backup**

**3:00 PM - Confirmed 3 A2 questions**
```bash
python scripts/backup_manager.py incremental
```
→ Creates `backup_103.json` (50 A1, 35 A2, 18 A3) - **Incremental backup**

**End of Day:**
```bash
python scripts/backup_manager.py list
```
```
Available Backups:
======================================================================
Version      Date         A1     A2     A3     Total
----------------------------------------------------------------------
backup_103   2026-02-09   50     35     18     443    ← Final state
backup_100   2026-02-09   50     32     18     443    ← After A1 complete
backup_98    2026-02-09   48     32     18     443    ← Morning start
```

### Day 2 (2026-02-10)

**9:00 AM - Start working**
```bash
python scripts/generate_a2_questions.py
```
→ Creates `backup_103.json`... wait, already exists!
→ Actually creates `backup_103.json` (new file with today's date) - **Daily backup**

---

## Commands Reference

### Automatic Backups (In Scripts)

```python
from scripts.backup_manager import create_backup_if_needed

def main():
    # Daily backup (runs once per day automatically)
    create_backup_if_needed()

    # ... your work ...
```

### Manual Incremental Backup

```bash
# After confirming questions in audit interface
python scripts/backup_manager.py incremental
```

Or in Python:
```python
from scripts.backup_manager import create_incremental_backup

# After confirming questions
create_incremental_backup()
```

### Force Backup Anytime

```bash
python scripts/backup_manager.py backup --force
```

### List All Backups

```bash
python scripts/backup_manager.py list
```

### Restore to Any Version

```bash
python scripts/backup_manager.py restore 100
```

---

## Workflow Integration

### For Audit Interface Users

After confirming questions, create incremental backup:

```bash
# 1. Open audit interface
python scripts/audit_questions_web.py

# 2. Confirm some questions via web UI

# 3. Create incremental backup (in another terminal)
python scripts/backup_manager.py incremental

# 4. Continue auditing...
```

### For Script Users

```python
# Your script that modifies questions
from scripts.backup_manager import create_backup_if_needed, create_incremental_backup

def main():
    # Daily backup at start
    create_backup_if_needed()

    # ... generate or modify questions ...

    # If you confirmed new questions, create incremental backup
    create_incremental_backup()
```

---

## Benefits

### Daily Backup
✓ **Safety net**: Always have a backup from start of day
✓ **Automatic**: Runs when you start working
✓ **No thinking**: Just works

### Incremental Backup
✓ **Fine-grained**: Restore to any point during the day
✓ **Progress tracking**: See your audit progress over time
✓ **Milestone capture**: Capture every significant change

### Combined
✓ **Best of both worlds**: Safety + precision
✓ **Flexible restoration**: Choose daily or specific milestone
✓ **Complete history**: Never lose confirmed questions

---

## Current Status

```
✅ Daily backup: Active (automatic)
✅ Incremental backup: Active (manual)
✅ Current state: backup_98.json (48 A1, 32 A2, 18 A3)
```

### Quick Test

```bash
# See your current backups
python scripts/backup_manager.py list

# Confirm a question, then:
python scripts/backup_manager.py incremental

# List again to see new backup
python scripts/backup_manager.py list
```

---

**You now have both protection AND precision!** 🎯
