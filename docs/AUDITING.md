# Question Auditing

## Results Viewer

After running the benchmark, launch the auditor to explore model outputs:

```bash
python scripts/audit/question_auditor_unified.py
# Opens at http://localhost:5000/results
```

The site auto-discovers the most recent run in `results/` — no path argument needed. To view a specific run:

```bash
python scripts/audit/question_auditor_unified.py --results results/experiment_20260513_142301/results.json
```

### What the Results tab shows

- **Dashboard** — model × condition leaderboard table with macro/micro scores and per-task-type breakdown. Color-coded cells highlight high and low scores. CSV download available.
- **Detail** — per-question results grouped by task type. Each row shows the score, model answer, and correctness. Click any row to open the full conversation: system prompt, user message, tool calls and responses, chain-of-thought trace, and final answer.

The site reloads results automatically when the file changes on disk, so you can leave it open while a long benchmark run is in progress.

---

## Quick Start

```bash
bash scripts/start_auditor.sh
# Opens at http://localhost:5000
```

Or manually:
```bash
python scripts/audit/question_auditor_unified.py
```

## Interface

The unified auditor at port 5000 has three modes:

- **Audit** (`/audit`) — review questions one by one
- **Review** (`/review`) — browse confirmed questions, filterable by task type
- **Results** (`/results`) — view LLM evaluation results with dashboard and detail views

### Results Viewer

Launch with experiment results:
```bash
python scripts/audit/question_auditor_unified.py data/questions/all_questions_system.json --results results/merge_all/results.json
```

The results mode has two sub-tabs:

- **Dashboard** — model comparison table with per-category scores, macro/micro/accuracy columns, color-coded cells, and CSV download button
- **Detail** — per-question results grouped by category, with Score/Nav/Val/Turns columns. Click any row to open the full conversation modal showing turn-by-turn history (system, user, assistant, tool messages, thinking blocks)

Scores show a "Preliminary" badge when `run_status` is not `"complete"`.

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
python scripts/audit/manage_queue.py status              # Show counts by task type
python scripts/audit/manage_queue.py preview             # Show next 20 in queue
python scripts/audit/manage_queue.py prioritize A2       # Move A2 pending/flagged to front
python scripts/audit/manage_queue.py deprioritize A1     # Move A1 to back
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
python scripts/data/add_questions_live.py /tmp/new_questions.json

# Reload questions file after external changes
python scripts/data/add_questions_live.py --reload
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

## Data Storage

**What's NOT in git** (by design — contains question content that should not be public):
- `data/questions/*.json` — question bank (all_questions_system.json)
- `data/audit_results/*.json` — audit state

**Canonical files:**
- `data/questions/all_questions_system.json` — the single source of truth for all questions
- `data/audit_results/audit_state.json` — audit status for each question

**Backups** are created by `scripts/data/backup_manager.py` if needed:
```bash
python scripts/data/backup_manager.py backup      # create backup
python scripts/data/backup_manager.py list        # list available backups
python scripts/data/backup_manager.py restore N   # restore to version N
```

## Troubleshooting

**Port in use:**
```bash
lsof -ti:5000 | xargs kill -9
bash scripts/start_auditor.sh
```

**Changes not showing in browser:** Hard-refresh (Cmd+Shift+R). If the queue order is wrong after `manage_queue.py prioritize`, a full auditor restart is more reliable than `/api/reload`:
```bash
pkill -f question_auditor_unified
python scripts/audit/question_auditor_unified.py
```

**Restore from backup:**
```bash
python scripts/data/backup_manager.py list     # find the right version
python scripts/data/backup_manager.py restore N
```
