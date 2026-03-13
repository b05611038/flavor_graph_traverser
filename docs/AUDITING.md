# Question Auditing

## Quick Start

```bash
bash scripts/start_auditor.sh
# Opens at http://localhost:5000
```

Or manually:
```bash
python scripts/question_auditor_unified.py
```

## Interface

The unified auditor at port 5000 has two modes:

- **Audit** (`/audit`) — review questions one by one
- **Review** (`/review`) — browse confirmed questions, filterable by task type

## Review Actions

| Action | Effect |
|---|---|
| **Confirm** | Mark as good. Question won't appear again. Auto-backup triggered. |
| **Flag** | Reject with a required reason. Won't appear again. |
| **Skip** | Keep as pending. Returns in next cycle. |

When all pending questions have been skipped once, the auditor cycles back to the beginning so you can make final decisions.

## Status Meanings

- **Confirmed** — approved for use, counts toward targets
- **Flagged** — rejected with documented reason
- **Pending** — needs review (new questions or previously skipped)

## Queue Management

Control which questions appear first using the CLI:

```bash
python scripts/manage_queue.py status              # Show counts by task type
python scripts/manage_queue.py preview             # Show next 20 in queue
python scripts/manage_queue.py prioritize A2       # Move A2 pending/flagged to front
python scripts/manage_queue.py deprioritize A1     # Move A1 to back
```

Or the API:

```python
from FlavorGraphTraverser.evaluation.queue_manager import QueueManager

qm = QueueManager(
    questions_file="data/questions/all_questions_system.json",
    audit_state_file="data/audit_results/audit_state.json"
)
qm.move_to_front(task_types=['A2_ancestor_verification'], exclude_statuses=['confirmed'])
qm.save()
```

## Adding Questions Without Restarting

```bash
# Add new questions from a file
python scripts/add_questions_live.py /tmp/new_questions.json

# Reload questions file after external changes
python scripts/add_questions_live.py --reload
```

This calls `POST /api/add_questions` or `POST /api/reload` on the running auditor.

## Audit State

All audit state is stored in a single canonical file:

```
data/audit_results/audit_state.json
```

The state manager uses file locking and atomic writes to prevent corruption.

**State file format:**
```json
{
  "question_id": {
    "status": "confirmed",
    "timestamp": "2026-02-05T10:35:53",
    "notes": "optional",
    "flag_reason": "required when flagged"
  }
}
```

## Backups

Backups are created automatically after each confirmation (incremental) and at the start of each generation script run (timestamped).

**Backup locations:**
```
data/backups/backup_N.json          # N = confirmed count at time of backup
data/backups/audit_state_N.json
data/questions/all_questions_system.json.backup_YYYYMMDD_HHMMSS
```

The version number in `backup_N.json` equals the confirmed question count at the time of backup. For example, `backup_98.json` was created when 98 questions were confirmed. Each backup includes a metadata header with confirmed counts by task type.

**Manual backup:**
```bash
python scripts/backup_manager.py backup      # create backup
python scripts/backup_manager.py list        # list available backups
python scripts/backup_manager.py restore 98  # restore to version with 98 confirmed
```

To add auto-backup to a script that modifies questions:
```python
from scripts.backup_manager import create_backup_if_needed
create_backup_if_needed()  # runs once per day
```

**What's NOT in git** (by design — too large/frequently changing):
- `data/questions/*.json`
- `data/audit_results/*.json`
- Backup files

## Troubleshooting

**Port in use:**
```bash
lsof -ti:5000 | xargs kill -9
bash scripts/start_auditor.sh
```

**Changes not showing in browser:** Hard-refresh (Cmd+Shift+R). If the queue order is wrong after `manage_queue.py prioritize`, a full auditor restart is more reliable than `/api/reload`:
```bash
pkill -f question_auditor_unified
python scripts/question_auditor_unified.py
```

**Restore from backup:**
```bash
python scripts/backup_manager.py list     # find the right version
python scripts/backup_manager.py restore N
```
