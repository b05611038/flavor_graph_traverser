# A1 Question Audit - Complete Documentation

## Overview

This document describes the A1 (root classification) question generation and auditing process completed on 2026-02-03.

## Final Results

**Status:** ✅ **50/50 A1 questions confirmed and validated**

### Distribution by Root Category

| Category | Count | Percentage |
|----------|-------|------------|
| fruity | 15 | 21.7% |
| sweet | 13 | 18.8% |
| green/vegetable | 8 | 11.6% |
| roasted | 7 | 10.1% |
| sour/fermented | 6 | 8.7% |
| floral | 6 | 8.7% |
| nutty/cocoa | 5 | 7.2% |
| other | 5 | 7.2% |
| spices | 5 | 7.2% |

**Total category appearances:** 70 (multi-label questions count towards multiple categories)
**Average per category:** 7.8

## Question Format

A1 questions use a **multi-label format** where:
- Questions present 5-6 root category options
- Correct answer can be 0, 1, or multiple categories (select all that apply)
- Tests LLM's ability to understand DAG structure where descriptors can belong to multiple root categories

**Example:**
```
Which of the following are root categories that 'hops' belongs to? (Select all that apply)

  (A) sweet
  (B) green/vegetable
  (C) roasted
  (D) floral
  (E) fruity
  (F) sour/fermented

Correct answer: [D, F] → floral + sour/fermented
```

## Data Leakage Prevention

### Exclusion Strategy

To prevent LLMs from using memorized tool knowledge, we excluded:

1. **Tool graph leaf nodes (85):** All leaf nodes from `coffee_flavor_wheel.pkl` that could be looked up directly
2. **Non-flavor categories (53):**
   - `taste` and all descendants (51 nodes): These are attributes, not flavors
   - `baked` (1 node): Empty category
   - `ROOT:SYSTEM` (1 node): Structural node

**Total excluded:** 137 nodes
**Available for questions:** 1,038 flavor descriptors

### Display Mapping

- `defected` → `other` (for user-facing text)
- Conditional footnote added when 'other' appears: *"'other' includes non-standard or less common flavor categories"*

## Generation Process

### Phase 1: Initial Generation
- Generated 75 A1 questions from SYSTEM graph (target: 50)
- Excluded tool leaf nodes and non-flavor categories
- Used diversity constraints (max 3 reuses per descriptor)

### Phase 2: NONE-Answer Questions
- Added 10 questions where correct_answer = [] (no options apply)
- Tests LLM's ability to identify when a descriptor doesn't match any shown categories

### Phase 3: Category Balancing
- Identified under-represented categories:
  - sour/fermented: 3 (lowest)
  - nutty/cocoa: 4
  - spices: 3
  - floral: 2
- Prioritized rare categories in pending queue

### Phase 4: Simple Descriptors
- Generated 12 questions with "wine-like" descriptors (single words)
- Examples: brandy, champagne, oolong, orchid, cointreau
- Goal: Reduce complex "adj + noun" combinations

### Phase 5: Final Diverse Generation
- Generated 8 additional diverse questions from unused descriptors:
  - 3x sour/fermented (pickled fruit, pickled crispy plum, mineral acid)
  - 2x nutty/cocoa (caramel chocolate, hazelnut chocolate)
  - 2x floral (pe'ur tea, rose petal)
  - 1x spices (corn soup)

### Phase 6: Duplicate Removal
- **Issue discovered:** "Brandy" appeared twice
- **Resolution:** Replaced with "hops" (floral + sour/fermented)
- Added deduplication check to `QuestionGenerator.deduplicate_questions()`

## Human Audit Process

### Web Interface

Two Flask applications were developed:

1. **Auditor (port 5000):** `scripts/audit_questions_web.py`
   - Review pending questions one at a time
   - Actions: Confirm, Flag, Skip
   - Shows annotated view with templates and objects
   - Removed keyboard shortcuts to prevent conflicts with copy/paste

2. **Review Site (port 5001):** `scripts/review_audited_questions.py`
   - View all confirmed and flagged questions
   - Actions: Unconfirm, Unflag, Confirm Flagged
   - Filter by task type and search
   - Auto-refresh every 10 seconds

### Audit State Management

- **Location:** `data/audit_results/` (excluded from git)
- **Files:**
  - `audit_state_YYYYMMDD.json`: Human review decisions
  - `flagged_questions_YYYYMMDD.jsonl`: Questions needing review
  - `confirmed_A1_questions_50.json`: Final confirmed A1 questions

## Quality Checks

### Issues Found and Resolved

1. **Duplicate descriptors:** Fixed "Brandy" duplication
2. **Data leakage:** Removed questions with tool leaf nodes (clove, winey, peanuts)
3. **Category imbalance:** Balanced by generating targeted questions
4. **Technical terms:** Kept "mineral acid" as acceptable (chemistry background helpful for coffee)

### Final Quality Metrics

- ✅ **No duplicate descriptors**
- ✅ **All 50 questions manually reviewed and confirmed**
- ✅ **Balanced distribution** (5-15 per category, 3x spread)
- ✅ **Diverse descriptor types** (simple, complex, technical, brand names)
- ✅ **Multi-label coverage** (0-3 correct answers per question)

## Files and Locations

### Safe Storage (Not in Git)

```
data/audit_results/
├── audit_state_20260203.json          # Human review decisions
├── flagged_questions_20260203.jsonl   # Questions flagged for review
└── confirmed_A1_questions_50.json     # Final 50 confirmed A1 questions
```

### Generated Questions (In Git)

```
data/questions/
└── all_questions_system.json          # All generated questions (367 total)
    └── A1_root_classification: 50 confirmed + others
```

### Scripts

```
scripts/
├── generate_all_questions.py          # Main generation script
├── audit_questions_web.py             # Auditor interface
├── review_audited_questions.py        # Review interface
├── filter_confirmed_questions.py      # Extract confirmed questions
└── [various helper scripts]           # Category balancing, deduplication
```

## Usage

### Generate Questions
```bash
python scripts/generate_all_questions.py
```

### Start Audit
```bash
# Auditor (port 5000)
python scripts/audit_questions_web.py data/questions/all_questions_system.json

# Review site (port 5001)
python scripts/review_audited_questions.py data/questions/all_questions_system.json
```

### Extract Confirmed Questions
```bash
python scripts/filter_confirmed_questions.py \
  --task-type A1_root_classification \
  --output data/audit_results/confirmed_A1_questions_50.json
```

## Lessons Learned

1. **Prevent duplicates early:** Use deduplication in generation pipeline
2. **Balance categories proactively:** Monitor distribution during generation
3. **Simple descriptors preferred:** Single-word descriptors are clearer
4. **Manual review essential:** Automated generation can't catch all quality issues
5. **Multi-label complexity:** DAG structure requires careful handling
6. **Web interface efficiency:** Faster than command-line review
7. **Safe data storage:** Keep audit results outside of git

## Next Steps

- [ ] Audit A2-A5 questions (taxonomic)
- [ ] Audit E1-E3 questions (similarity)
- [ ] Audit F questions (open-ended)
- [ ] Run experiments with confirmed question set
- [ ] Document best practices for future question generation

## Contributors

- Human auditor: Manual review and quality assurance
- Claude Code: Automated generation, web interfaces, analysis

## Date Completed

2026-02-03
