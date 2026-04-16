# Parse Error Tracking Memo

**Date:** 2026-04-15  
**Initial non-success files:** 70  
**Final non-success files:** 20 (all accepted as model behavior)  
**Run directory:** `results/run_20260413_141616`

---

## Final Status

| Group | Count | Resolution |
|-------|-------|------------|
| Truncated format — parser fixed | 18 | ✅ Fixed (zero API cost) |
| Empty API response — re-run | 15 | ✅ Fixed via re-run |
| Format noncompliance — re-run | 16 | ✅ Fixed via re-run |
| GPT-5.4 safety refusals | 16 | ✅ Accepted, score=0 |
| Tool errors (malformed tool calls) | 3 | ✅ Accepted, score=0 |
| Truncated format — unrecoverable (1 file, empty bracket) | 1 | ✅ Accepted, score=0 |

---

## Parser Fix — `parse_multiselect_answer()` (2026-04-15)

**File:** `FlavorGraphTraverser/evaluation/utils/answer_parser.py`

**Reason:** LLMs do not always follow the required output format exactly. Three systematic format violations were observed across multiple models and needed to be accommodated in the parser. This is reported as a known limitation in the evaluation pipeline — scores for affected questions reflect the model's actual answer intent, not a parser failure.

### Violation 1 — Truncated format (17 files, gpt-oss-120b)

**Observed:** `"Therefore, I select (D"` — closing `)` missing (response cut off at token limit)  
**Sub-cases:**
- `"I select (D"` → single-letter truncated → parsed as `['D']`
- `"I select (NONE"` → NONE keyword truncated → parsed as `[]`
- `"I select ("` → completely empty bracket → **unrecoverable** (1 file, score=0)

**Fix added:**
```python
(r"I select \(([^)]+)\s*$", "I select (... (truncated)"),
```

**Recovered:** 16/17 files. 1 file (`A1_root_classification_59c53f36`) had `"I select ("` with nothing after the bracket — unrecoverable, accepted as score=0.

### Violation 2 — Bold markdown format (2 files, mistral-medium-3.1)

**Observed:** `"Therefore, I select **(D, E)**"` — model wrapped selection in bold markdown instead of plain parentheses  
**Fix added:**
```python
(r"I select \*\*\(([^)]+)\)\*\*", "I select **(...)**"),
```

**Recovered:** 2/2 files.

### Violation 3 — Thinking-content truncation (6 files, kimi-k2.5)

**Observed:** kimi-k2.5 (a reasoning model with extended thinking) exhausted its visible output token budget mid-sentence, but completed its answer in `thinking_content` (internal chain-of-thought). The parser only reads visible `content`, so it fell back to "Last (X)" / "Last letter" patterns and extracted a spurious letter from the reasoning text instead of the model's actual final answer.

**Example:** Visible content ends mid-sentence; `thinking_content` ends with `"Therefore, I select (A)"`. Parser matched `(B)` from a parenthetical mention in reasoning → recorded B instead of A.

**Fix:** Manual correction of 6 cache files (all kimi-k2.5 no_tool). Each file's `model_answer` updated to match the answer in `thinking_content`, with `pattern_matched` set to `"I select (X) [from thinking_content]"` for traceability.

**Impact:**
- 2 files flipped correct→wrong (fallback had coincidentally matched the right answer)
- 2 files flipped wrong→correct (model actually knew the answer)
- 2 files remained wrong (different wrong answer either way)

**Affected files:**
| Question | Old answer | True answer (thinking) | Correct answer | Flip |
|----------|-----------|----------------------|---------------|------|
| E1_similarity_ranking_da0cd1a7 | A | C | A | correct→wrong |
| A3_sibling_identification_5e172258 | C | D | C | correct→wrong |
| E1_similarity_ranking_2edf3881 | A | C | D | — |
| E2_pairwise_comparison_f6965816 | B | A | C | — |
| A3_sibling_identification_b6012c29 | B | D | D | wrong→correct |
| E1_similarity_ranking_df03ccc4 | A | D | D | wrong→correct |

---

## Re-runs Performed (2026-04-15)

| Round | Models | Condition | Questions | Outcome |
|-------|--------|-----------|-----------|---------|
| rerun4 | kimi-k2.5 | tool | 21 (402 payment errors) | ✅ Done |
| rerun5 | kimi, mistral, qwen, nemotron | no_tool + tool | 34 (empty/noncompliant) | ✅ Done (partial — 16 newly fixed) |
| rerun6 (kimi) | kimi-k2.5 | no_tool | 7 (persistent empty, max_tokens=32768) | ✅ Done |
| rerun6 (nemotron) | nemotron | no_tool | 1 (max_tokens=65536) | ✅ Done (answered via fp4 provider) |
| rerun7 | nemotron | no_tool | 1 (persistent, fp4 routing confirmed) | ✅ Done |

**Key finding — nemotron token limit:** OpenRouter routes nemotron to DeepInfra (bf16) or Nebius Token Factory (fp4). The bf16 provider hit a 16,384-token limit where nemotron looped endlessly without answering. After raising `max_output_tokens` to 65,536, OpenRouter routed to the fp4 provider (faster, 182 tps), which answered in 1,342 tokens with a direct response (though incorrect). This suggests OpenRouter's provider selection depends on the requested token budget.

---

## Accepted as Final — Score=0

### GPT-5.4 Safety Refusals (16 files)

Model refused with `"I'm sorry, but I cannot assist with that request."` Temperature=0 — deterministic, re-running will not change outcome.

| Condition | Question ID |
|-----------|-------------|
| no_tool | A2_ancestor_verification_2c3631ce |
| no_tool | A2_ancestor_verification_4bbff8fc |
| no_tool | A2_ancestor_verification_85be0943 |
| no_tool | A3_sibling_identification_021d0835 |
| no_tool | A3_sibling_identification_58adefa5 |
| no_tool | E1_similarity_ranking_717fecf1 |
| no_tool | E2_pairwise_comparison_0006928d |
| no_tool | E2_pairwise_comparison_251b26e8 |
| no_tool | E2_pairwise_comparison_4c443873 |
| no_tool | E2_pairwise_comparison_4cb4a63d |
| no_tool | E2_pairwise_comparison_bf8b3688 |
| no_tool | E2_pairwise_comparison_e53a9814 |
| no_tool | E2_pairwise_comparison_eb9580e7 |
| no_tool | E2_pairwise_comparison_f7e73fae |
| tool | A2_ancestor_verification_441d29c8 |
| tool | A4_multiselect_01a7dbe3 |

### Tool Errors — Malformed Tool Calls (3 files)

| Model | Condition | Question ID | Error |
|-------|-----------|-------------|-------|
| deepseek-v3.2 | tool | E2_pairwise_comparison_4c443873 | Called `validate_descript\ors` (backslash in tool name) |
| kimi-k2.5 | tool | A3_sibling_identification_c3d2f748 | Called `get_parent()` with no arguments |
| kimi-k2.5 | tool | E2_pairwise_comparison_251b26e8 | Called `get_parent()` with no arguments |

### Unrecoverable Truncated Format (1 file)

| Model | Condition | Question ID | Content |
|-------|-----------|-------------|---------|
| gpt-oss-120b | tool | A1_root_classification_59c53f36 | `"Therefore, I select ("` — empty bracket, no answer extractable |

---

## Notes for Paper / Report

- **Parser relaxation is reported transparently:** Three format violations were fixed. (1) gpt-oss-120b truncated closing `)` — 16 files recovered by extending `parse_multiselect_answer()`. (2) mistral-medium-3.1 wrapped answers in bold markdown `**(...)**` — 2 files recovered. (3) kimi-k2.5 exhausted visible output tokens but completed its answer in `thinking_content` (extended thinking) — 6 files corrected manually. In all cases the fix recovers the model's actual answer intent, not a different answer.
- **Safety refusals (gpt-5.4, 16 files):** These questions score 0 and should be noted as a model limitation, not benchmark difficulty. The refusals occurred on flavor/sensory questions, not obviously sensitive content.
- **Malformed tool calls (3 files):** Represent model-level tool use errors. Score 0 appropriately.
- **Total final non-success rate:** 20/6050 = 0.33% of all cache files.
