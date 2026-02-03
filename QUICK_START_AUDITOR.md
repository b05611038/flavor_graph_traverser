# Quick Start: Question Auditor

**Get started auditing questions in 2 minutes**

## Install Dependencies

```bash
pip install flask pyyaml requests
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Try It Now (Sample Questions)

We've included 5 sample questions to test the auditor:

```bash
python scripts/audit_questions_web.py data/sample_questions_for_audit.json
```

Open browser: `http://localhost:5000`

**What you'll see:**
- 5 sample questions
- Including intentional duplicate (TEST_A1_003)
- Including ambiguous question (TEST_A1_004)

Try the workflow:
1. ✅ Confirm the first two questions (press `C` or click button)
2. 🚩 Flag the ambiguous question (press `F`)
3. See duplicate warning on TEST_A1_003

## Your Questions

Once you have your own questions:

```bash
# 1. Start web auditor
python scripts/audit_questions_web.py data/questions/your_questions.json

# 2. Review in browser (http://localhost:5000)
#    - Confirm good questions
#    - Flag problematic ones

# 3. Review flagged questions
python scripts/review_flagged.py

# 4. Check progress
#    State saved to: data/audit_state.json
#    Flagged saved to: data/flagged_questions.jsonl
```

## Key Features

### Web Interface

**Two Views:**
- 📄 **What LLM Sees** - Imagine yourself as the model
- 🔍 **Annotated View** - See template, objects, correct answer

**Actions:**
- `C` - Confirm (good question)
- `F` - Flag (problem)
- `S` - Skip

**Automatic:**
- Duplicate detection
- Progress tracking
- State persistence

### CLI Review

For flagged questions:

```bash
python scripts/review_flagged.py
```

**Options:**
1. Discuss with Claude (copy question, discuss in chat)
2. Save notes
3. Unflag and accept
4. Keep flagged
5. Export JSON

## Files Created

```
data/
├── audit_state.json              # Your review progress
├── flagged_questions.jsonl       # Questions you flagged
├── question_review_notes.jsonl   # Your notes
└── exports/                      # Exported questions
```

## Workflow

```
Generate → Web Audit → CLI Review → Confirmed Questions
           (80% work)  (20% work)
```

**Web Audit: Fast review**
- Visual inspection
- Confirm most questions
- Flag edge cases

**CLI Review: Deep review**
- Discuss with Claude
- Fix template issues
- Regenerate if needed

## Example Session

```bash
$ python scripts/audit_questions_web.py data/sample_questions_for_audit.json

Loading questions from: data/sample_questions_for_audit.json
Loaded 5 questions

Audit Status:
  Confirmed: 0
  Flagged: 0
  Pending: 5

======================================================================
🔍 Question Auditor Web Interface
======================================================================

Open in browser: http://localhost:5000

Press Ctrl+C to stop
======================================================================
```

**In browser:**
- Review questions
- Confirm 3, flag 2
- Close browser (Ctrl+C in terminal)

**Review flagged:**

```bash
$ python scripts/review_flagged.py

======================================================================
🔍 FLAGGED QUESTION REVIEWER
======================================================================

Loading flagged questions from: data/flagged_questions.jsonl

🔍 Found 2 flagged question(s)

[Shows each question with full details]

ACTIONS:
[1] Discuss with Claude (stay in CLI)
[2] Save notes about this question
[3] Unflag and accept as-is
[4] Keep flagged, review later
[5] Export question JSON for inspection
[Q] Quit review session

Your choice:
```

## Tips

**Web Review:**
- Do it in batches (20-30 at a time)
- Use keyboard shortcuts (`C`, `F`, `S`)
- Flag anything questionable - better safe than sorry

**CLI Review:**
- Choose [1] to discuss with Claude
- Copy the question display
- Paste into Claude chat
- Ask: "Is this question clear?" "Is answer correct?"

**With Claude:**
- Claude sees the full question context
- Discuss ambiguities
- Get suggestions for fixes
- Decide whether to regenerate

## Full Documentation

See `docs/QUESTION_AUDITOR_GUIDE.md` for:
- Detailed workflow
- Advanced usage
- Troubleshooting
- File formats
- Custom duplicate detection

## Next Steps

After auditing:

1. **Export confirmed questions:**
   ```python
   # Get confirmed question IDs
   from FlavorGraphTraverser.evaluation.question_auditor import QuestionAuditor
   auditor = QuestionAuditor()
   confirmed = auditor.get_confirmed_questions()
   ```

2. **Run experiments:**
   ```bash
   python scripts/run_experiments.py --questions data/questions/confirmed.json
   ```

3. **Generate more questions:**
   - Based on what worked well
   - Adjust templates for flagged issues
   - Iterate until you have enough high-quality questions

---

**That's it! Start auditing your questions now.**

For help:
- See `docs/QUESTION_AUDITOR_GUIDE.md`
- Ask Claude
- Check `data/audit_state.json` for progress
