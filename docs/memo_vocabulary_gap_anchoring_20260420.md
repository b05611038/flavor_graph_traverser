# Research Memo: Vocabulary Gap Anchoring Mechanism

**Date:** 2026-04-20  
**Status:** Empirically confirmed — implemented in `deep_analysis.py` as `vocabulary_gap_analysis()`

---

## Core Claim

The benchmark's central finding is **not** simply "tools hurt performance." The mechanism is more specific and more defensible:

> The tool graph (111-node SCAA wheel) is a strict vocabulary subset of the real-world flavor space used to author questions (1,175-node system graph). When a model calls `validate_descriptors` on a legitimate flavor descriptor absent from the SCAA wheel, the tool returns an "invalid" signal. Models treat this false-negative as evidence that no answer exists, and select NONE — even when a correct answer is reachable through their parametric knowledge.

This is **vocabulary gap anchoring**: the model over-trusts a negative tool signal caused by coverage limitations, not by the question being unanswerable.

---

## Why the "In/Out of Vocabulary" Split Is Degenerate at the Question Level

By design, 100% of target descriptors in the question set are drawn from system-graph-only nodes — none appear in the 111-node tool graph. This means you cannot split questions into "target in vocabulary" vs. "target out of vocabulary" because all questions hit the vocabulary gap. The universal coverage gap is an intentional feature of the benchmark design, not an oversight.

**Implication for paper writing:** Frame this as a design choice that creates a controlled test: the vocabulary gap is constant across all questions, so any variation in the tool-condition score drop must come from other factors (task structure, answer-option vocabulary, model behavior).

---

## Two Direct Empirical Tests (Already in the Data)

### 1. NONE-Response Inflation (Behavioral Evidence)

The clearest behavioral signature of vocabulary gap anchoring is the rate at which models select NONE (no valid answer) across conditions.

**Key numbers (from `deep_analysis.py` output):**
- NONE rate under no_tool: ~6.1%
- NONE rate under tool: ~23.3%
- Of tool-condition NONE responses: ~81% are wrong

The ~4× inflation of NONE selections under the tool condition — and the fact that the vast majority are incorrect — directly demonstrates the anchoring mechanism. Models that would have answered correctly from parametric knowledge instead commit to "nothing matches" after receiving invalid tool signals.

**Per-task interpretation:** A4 shows the most extreme NONE inflation (correct paths drop from ~45% to ~15%) because every leaf descriptor in A4 options falls outside the tool vocabulary. The model exhaustively validates all candidates, gets all-invalid, and defaults to NONE.

### 2. A1 Correct-Answer Vocabulary Split (Strongest Direct Test)

For A1 (root-category classification), the answer *options* are root category names — 7 of 9 root categories appear in the tool graph, but 2 (`floral`, `green/vegetable`) do not. This creates a clean natural experiment within A1 alone.

**Results (from `deep_vocab_gap_a1_split.csv`):**

| Group | n pairs | no_tool acc | tool acc | Δ |
|---|---|---|---|---|
| Correct root IS in tool graph | ~429 | ~0.389 | ~0.510 | **+0.121** |
| Correct root NOT in tool graph | ~121 | ~0.413 | ~0.231 | **−0.182** |

The ~0.30 swing in Δ depending solely on tool-graph vocabulary membership is the single strongest empirical test of the vocabulary gap hypothesis. When the model can validate the correct answer, it confirms and selects it (tool helps). When the model validates the correct answer and gets "invalid" back, it rejects it and switches to a wrong answer (tool hurts).

**Caution:** `floral` and `green/vegetable` may also differ from the other 7 roots in question difficulty or descriptor distribution, not only vocabulary membership. Acknowledge this as a possible confound, but note that the direction and magnitude of the effect are consistent with the vocabulary gap mechanism across all task types.

---

## Two Mechanistically Distinct Phenomena (Do Not Conflate)

### Vocabulary Gap Anchoring (this memo)
- **Mechanism:** Model calls tool → gets "invalid" → incorrectly concludes no answer → selects NONE
- **Signature:** NONE inflation (6% → 23%), concentrated in tasks where leaf descriptors are out of vocabulary
- **Evidence:** A1 vocabulary split, A4 extreme drop, NONE wrong-rate
- **Models affected:** All models that call tools (90% of tool-condition evaluations)

### Prompt-Level Anchoring (separate — `prompt_anchoring_analysis()`)
- **Mechanism:** The tool-condition system prompt's epistemic framing ("only treat confirmed results as positive evidence") causes models to second-guess parametric knowledge even when they never call any tools
- **Signature:** Negative Δ even in zero-call subsets (reasoning_calls = 0)
- **Evidence:** GPT-5.4 shows negative Δ with zero calls; Nemotron (also low call rate) shows near-zero Δ
- **Models affected:** Models whose parametric confidence is destabilized by the system prompt framing

These two mechanisms are **additive** in models that both call tools and are sensitive to prompt framing (e.g., GPT-5.4 under A2/A4). Disentangling them requires comparing zero-call vs. non-zero-call subsets *within* the same model, which `prompt_anchoring_analysis()` does.

---

## Implications for Paper Framing

1. **Lead with the mechanism, not the direction.** "Tools hurt performance" is a weak claim. "A coverage-limited tool creates false-negative signals that anchor models toward NONE responses" is specific, testable, and novel.

2. **The A1 vocabulary split is Figure-worthy.** A paired bar chart of Δ for in-vocab vs. out-of-vocab A1 questions, with individual model dots, directly visualizes the mechanism. Consider adding this as Figure 4 or a panel in Figure 1.

3. **A4 is the extreme natural experiment.** Every A4 leaf descriptor is out of vocabulary. The 3× accuracy drop (0.45 → 0.15) and 91% NONE rate among wrong answers make A4 the clearest illustration of the mechanism. Lead the mechanistic section with A4.

4. **Do not frame as "richer tool graph would fix it."** The vocabulary gap is intentional — it tests whether models can reason about concepts beyond the tool's coverage. A tool that perfectly covers the question space would be question-answering, not tool-assisted reasoning.

5. **The Recovery Index** (reasoning_calls / val_call_count) measures whether models that receive invalid validation signals subsequently use graph-traversal tools (get_parent, get_children) to recover. Low recovery index = model gives up after invalid signal. This is a secondary supporting analysis for the anchoring claim.

---

## Output Files

| File | Contents |
|---|---|
| `results/analysis/deep_none_inflation.csv` | NONE rate by condition, n_none, pct_wrong |
| `results/analysis/deep_none_inflation_by_task.csv` | NONE rate per task type × condition |
| `results/analysis/deep_vocab_gap_a1_split.csv` | A1 in/out-vocab split: n, no_tool acc, tool acc, Δ |
| `results/analysis/deep_anchoring_recovery.csv` | Recovery Index per model |
| `results/analysis/deep_anchoring_by_task.csv` | Spearman(invalid_ratio, tool_score) per task |
| `results/analysis/deep_anchoring_scatter.pdf` | Scatter: invalid_ratio vs tool_score, colored by task |
