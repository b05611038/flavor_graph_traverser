# Question Auditor Guide

**Interactive workflow for quality-checking generated questions**

## Overview

The Question Auditor provides a two-stage workflow for reviewing generated questions:

1. **Web Interface** - Quick visual review, confirm or flag questions
2. **CLI Tool** - Deep review of flagged questions with Claude's help

### Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                     QUESTION AUDITOR WORKFLOW                    │
└─────────────────────────────────────────────────────────────────┘

1. Generate questions → data/questions/your_questions.json

2. Web Auditor (http://localhost:5000)
   ├─ Review question visually
   ├─ See LLM view (what model sees)
   ├─ See annotated view (template + objects + correct answer)
   ├─ Check for duplicates (automatic)
   │
   ├─ ✅ CONFIRM → Mark as good, move to next
   │   └─ Saved to data/audit_state.json
   │
   └─ 🚩 FLAG → Mark for CLI review
       └─ Logged to data/flagged_questions.jsonl

3. CLI Review Tool
   ├─ Load flagged questions
   ├─ Discuss with Claude
   ├─ Save notes or unflag
   └─ Export for manual editing

4. Repeat until all confirmed
```

---

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

This installs:
- `flask` - Web server
- `pyyaml` - Config loading
- `requests` - API calls

---

## Part 1: Web Interface

### Starting the Auditor

```bash
python scripts/audit_questions_web.py data/questions/your_questions.json
```

**Options:**
```bash
# Custom state file location
python scripts/audit_questions_web.py data/questions/your_questions.json \
  --state-file data/custom_audit.json

# Custom port
python scripts/audit_questions_web.py data/questions/your_questions.json \
  --port 8000
```

### Using the Web Interface

**Open in browser:** `http://localhost:5000`

#### What You'll See

**Header (Progress Bar)**
- Confirmed count
- Flagged count
- Pending count
- Progress percentage

**Question Display**

Two views for each question:

1. **📄 What the LLM Sees**
   - The exact text sent to the model
   - Question + options
   - Answer format instruction
   - This is what you imagine yourself as the LLM reading

2. **🔍 Annotated View**
   - 📋 TEMPLATE: The template used
   - 🎯 OBJECTS: Graph objects filled in (e.g., `descriptor1 = 'chocolate'`)
   - ❓ FINAL QUESTION: The rendered question
   - 📝 OPTIONS: All options
   - ✅ CORRECT ANSWER: The ground truth

**Duplicate Detection**
- Automatic check against confirmed questions
- Warning shown if duplicate found
- You can still confirm duplicates if intentional

#### Actions

**✅ Confirm - Looks Good**
- Question is valid
- Moves to next question
- Saved in audit state

**🚩 Flag for Review**
- Opens modal asking for reason
- Logs to `data/flagged_questions.jsonl`
- Moves to next question
- Review later in CLI

**Skip**
- Skip to next without action
- Question remains pending
- Will show up again later

**Keyboard Shortcuts:**
- `C` - Confirm
- `F` - Flag
- `S` - Skip
- `Esc` - Close modal

#### Example Question Display

```
┌─────────────────────────────────────────────────────────────────┐
│ Question ID: A1_coffee_001                                      │
│ Category: A  Task Type: root_classification                     │
│                                                   5 remaining    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ 📄 What the LLM Sees                                            │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Which root category does 'chocolate' belong to?            │ │
│ │                                                             │ │
│ │   (A) fruity                                                │ │
│ │   (B) floral                                                │ │
│ │   (C) nutty/cocoa                                           │ │
│ │   (D) spices                                                │ │
│ │                                                             │ │
│ │ When providing your final answer, use this exact format:   │ │
│ │ "Therefore, I select (X)" where X is A, B, C, or D.        │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ 🔍 Annotated View (Template + Objects)                          │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 📋 TEMPLATE:                                                │ │
│ │   Which root category does '{descriptor}' belong to?       │ │
│ │                                                             │ │
│ │ 🎯 OBJECTS (from graph):                                    │ │
│ │   descriptor = 'chocolate'                                  │ │
│ │   root_category = 'nutty/cocoa'                             │ │
│ │   distractor1 = 'fruity'                                    │ │
│ │   distractor2 = 'floral'                                    │ │
│ │   distractor3 = 'spices'                                    │ │
│ │                                                             │ │
│ │ ✅ CORRECT ANSWER: (C) nutty/cocoa                          │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ [✅ Confirm]  [🚩 Flag]  [Skip]                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 2: CLI Review Tool

### When to Use

After flagging questions in the web interface:
- Ambiguous wording
- Wrong correct answer
- Template issues
- Need to regenerate

### Starting the CLI Tool

```bash
python scripts/review_flagged.py
```

**Options:**
```bash
# Custom flagged log location
python scripts/review_flagged.py --flagged-log data/my_flags.jsonl

# Custom state file
python scripts/review_flagged.py --state-file data/custom_audit.json
```

### CLI Review Session

The tool shows each flagged question with full details:

```
======================================================================
📋 FLAGGED QUESTION REVIEW
======================================================================

Question ID: A1_coffee_042
Category: A
Task Type: root_classification
Flagged: 2026-01-31T10:30:00Z

🚩 FLAG REASON: Ambiguous wording - multiple interpretations
📝 NOTES: The word "belong" could mean direct parent or root category

----------------------------------------------------------------------
📄 WHAT LLM SEES:
----------------------------------------------------------------------

Which category does 'dark chocolate' belong to?

  (A) chocolate
  (B) nutty/cocoa
  (C) sweet
  (D) fruity

When providing your final answer, use this exact format:
"Therefore, I select (X)" where X is A, B, C, or D.

----------------------------------------------------------------------
🔍 ANNOTATED VIEW:
----------------------------------------------------------------------

📋 TEMPLATE:
  Which category does '{descriptor}' belong to?

🎯 OBJECTS (from graph):
  descriptor = 'dark chocolate'
  parent = 'chocolate'
  root = 'nutty/cocoa'

✅ CORRECT ANSWER: (B) nutty/cocoa

======================================================================
```

### Action Menu

For each flagged question:

```
======================================================================
ACTIONS:
======================================================================

[1] Discuss with Claude (stay in CLI)
[2] Save notes about this question
[3] Unflag and accept as-is
[4] Keep flagged, review later
[5] Export question JSON for inspection
[Q] Quit review session

Your choice:
```

**Option 1: Discuss with Claude**
- Puts you in discussion mode
- You can now copy the question and discuss with Claude
- Claude has full context from the display above
- Example discussions:
  - "Is this question actually ambiguous?"
  - "Should the correct answer be (A) or (B)?"
  - "How should I rephrase the template?"

**Option 2: Save Notes**
- Write notes about the problem
- Saved to `data/question_review_notes.jsonl`
- You can review notes later

**Option 3: Unflag and Accept**
- Question was actually fine
- Remove from flagged list
- Marks as accepted in audit state

**Option 4: Keep Flagged**
- Skip for now
- Will appear in next review session
- Useful if you need more time to think

**Option 5: Export JSON**
- Saves question to `data/exports/{question_id}.json`
- You can manually edit if needed
- Useful for complex fixes

### Example Discussion with Claude

After choosing option [1], you can discuss:

**You:**
> Looking at question A1_coffee_042 above. The template asks "Which category does 'dark chocolate' belong to?" but the correct answer is 'nutty/cocoa' which is the root, not the immediate parent 'chocolate'. Is this ambiguous?

**Claude:**
> Yes, this is ambiguous. "belong to" could mean:
> 1. Direct parent → answer should be (A) chocolate
> 2. Root category → answer should be (B) nutty/cocoa
>
> I recommend either:
> - Change template to "Which ROOT category..."
> - Or change task to use direct parent and make (A) correct
>
> Which approach fits your task type better?

**You:**
> This is task type A1 (root classification), so we want root. Let me update the template to say "root category" explicitly.

---

## File Structure

```
project/
├── data/
│   ├── questions/
│   │   └── your_questions.json          # Input: Generated questions
│   │
│   ├── audit_state.json                 # State: confirmed/flagged status
│   ├── flagged_questions.jsonl          # Log: Flagged questions
│   ├── question_review_notes.jsonl      # Notes: Your review notes
│   │
│   └── exports/                         # Exported questions for editing
│       ├── A1_coffee_042.json
│       └── E2_coffee_015.json
│
├── scripts/
│   ├── audit_questions_web.py           # Web interface
│   └── review_flagged.py                # CLI review tool
│
└── templates/
    └── auditor.html                     # Web interface template
```

---

## Audit State Format

**data/audit_state.json:**
```json
{
  "A1_coffee_001": {
    "question_id": "A1_coffee_001",
    "status": "confirmed",
    "timestamp": "2026-01-31T10:15:00Z",
    "notes": null
  },
  "A1_coffee_042": {
    "question_id": "A1_coffee_042",
    "status": "flagged",
    "timestamp": "2026-01-31T10:30:00Z",
    "flag_reason": "Ambiguous wording",
    "notes": "Need to specify 'root category' in template"
  }
}
```

**data/flagged_questions.jsonl:**
```jsonl
{"question_id": "A1_coffee_042", "question": {...}, "reason": "Ambiguous wording", "notes": "...", "timestamp": "2026-01-31T10:30:00Z"}
{"question_id": "E2_coffee_015", "question": {...}, "reason": "Wrong answer", "notes": "...", "timestamp": "2026-01-31T10:45:00Z"}
```

---

## Complete Workflow Example

### 1. Generate Questions

```bash
# Generate 100 questions for category A1
python scripts/generate_questions.py \
  --graph data/graphs/coffee_flavor_wheel.pkl \
  --output data/questions/A1_questions.json \
  --category A1 \
  --count 100
```

### 2. Start Web Auditor

```bash
python scripts/audit_questions_web.py data/questions/A1_questions.json
```

Output:
```
Loading questions from: data/questions/A1_questions.json
Loaded 100 questions

Audit Status:
  Confirmed: 0
  Flagged: 0
  Pending: 100

======================================================================
🔍 Question Auditor Web Interface
======================================================================

Open in browser: http://localhost:5000

Press Ctrl+C to stop
======================================================================
```

### 3. Review Questions in Browser

- Open `http://localhost:5000`
- Review each question
- Press "Confirm" for good questions (keyboard: `C`)
- Press "Flag" for problems (keyboard: `F`)

**Example flags:**
- "Ambiguous wording - unclear what 'category' means"
- "Wrong answer - should be B not C"
- "Duplicate of A1_coffee_012"

### 4. Check Progress

Web interface shows:
```
Confirmed: 85
Flagged: 5
Pending: 10
Progress: 85%
```

### 5. Review Flagged Questions (CLI)

After finishing web review:

```bash
python scripts/review_flagged.py
```

Output:
```
======================================================================
🔍 FLAGGED QUESTION REVIEWER
======================================================================

Loading flagged questions from: data/flagged_questions.jsonl

🔍 Found 5 flagged question(s)

======================================================================
REVIEW SESSION - Work with Claude to fix problems
======================================================================

[Shows each flagged question]
```

### 6. Discuss with Claude

For each flagged question:
1. Choose [1] Discuss with Claude
2. Copy question text
3. Discuss in your Claude conversation
4. Decide: unflag, save notes, or keep flagged

### 7. Regenerate if Needed

If you need to regenerate a question:

```bash
# Export the question
# In CLI: choose [5] Export question JSON

# Edit manually or regenerate with adjusted parameters
python scripts/generate_questions.py \
  --regenerate data/exports/A1_coffee_042.json \
  --template-fix "Which ROOT category does '{descriptor}' belong to?"
```

### 8. Final Confirmation

After reviewing all flagged questions:

```bash
# Restart web auditor
python scripts/audit_questions_web.py data/questions/A1_questions.json
```

Should show:
```
Confirmed: 100
Flagged: 0
Pending: 0
Progress: 100%
```

✅ All questions reviewed and ready for experiments!

---

## Tips for Effective Auditing

### What to Look For

**❌ Flag these:**
- Ambiguous wording
- Multiple correct answers
- Wrong correct answer marked
- Unclear what the question asks
- Options don't make sense
- Template not filled correctly
- Graph objects seem wrong

**✅ Confirm these:**
- Clear, unambiguous question
- One obviously correct answer
- Three plausible distractors
- Matches the task type
- Template filled correctly
- You could answer it as an LLM

### Imagine Yourself as the LLM

When reviewing:
1. Read "What the LLM Sees" first
2. Try to answer without looking at annotated view
3. Check if your answer matches the correct answer
4. If not, is the question ambiguous or is the answer wrong?

### Use Keyboard Shortcuts

- `C` - Confirm (most common action)
- `F` - Flag (when something's wrong)
- `S` - Skip (need more time to think)

Much faster than clicking!

### Review in Batches

- Do 20-30 questions at a time
- Take breaks
- Come back with fresh eyes
- CLI review when you have time to think

---

## Troubleshooting

### Web Interface Won't Start

```bash
# Check if port is in use
lsof -i :5000

# Use different port
python scripts/audit_questions_web.py data/questions/A1_questions.json --port 8000
```

### Questions Not Loading

Check file format:
```json
{
  "questions": [
    {
      "id": "A1_001",
      "text": "...",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct_answer": "C",
      "category": "A",
      "task_type": "root_classification"
    }
  ]
}
```

### Duplicate Detection Not Working

Duplicate check compares:
- Question text (case-insensitive)
- Option values (order-independent)

Only checks against **confirmed** questions, not flagged or pending.

### Lost Audit State

If `data/audit_state.json` gets deleted:
- All questions become pending again
- You'll need to re-review
- **Backup this file regularly!**

---

## Advanced Usage

### Batch Review Script

Create a script to review multiple question sets:

```bash
#!/bin/bash
for file in data/questions/*.json; do
    echo "Reviewing: $file"
    python scripts/audit_questions_web.py "$file"
done
```

### Custom Duplicate Logic

Edit `FlavorGraphTraverser/evaluation/question_auditor.py`:

```python
def check_duplicate(self, question, confirmed_questions):
    # Add custom duplicate detection logic
    # e.g., fuzzy matching, semantic similarity
    pass
```

### Export Confirmed Questions

Get all confirmed questions:

```python
from FlavorGraphTraverser.evaluation.question_auditor import QuestionAuditor
import json

auditor = QuestionAuditor()
confirmed_ids = auditor.get_confirmed_questions()

# Load original questions
with open('data/questions/A1_questions.json') as f:
    all_questions = json.load(f)['questions']

# Filter to confirmed only
confirmed = [q for q in all_questions if q['id'] in confirmed_ids]

# Save
with open('data/questions/A1_confirmed.json', 'w') as f:
    json.dump({'questions': confirmed}, f, indent=2)
```

---

## Summary

**Two-stage workflow:**
1. **Web**: Quick visual review, confirm or flag
2. **CLI**: Deep review of flagged questions with Claude

**Key features:**
- See what LLM sees vs annotated view
- Automatic duplicate detection
- Track progress
- Flag for detailed review
- Discuss problems with Claude
- Export for manual editing

**Result:**
- High-quality, reviewed question set
- Confidence in experimental results
- Documentation of issues and fixes
