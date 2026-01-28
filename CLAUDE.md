# CLAUDE.md

## Project Goal

Benchmark tool-augmented LLM inference on coffee flavor hierarchy reasoning. Compare against direct prompting and full-context baselines.

## Expected Outputs

### Table 1: Main Results
Accuracy (%) by Model × Condition (C0-C5)

### Table 2: Per-Task Breakdown
Accuracy for C0 vs C3 vs C5 across task types:
- A1-A5: Taxonomic reasoning (root classification, ancestor verification, sibling identification, path reconstruction, LCA)
- E1-E3: Similarity reasoning (ranking, pairwise comparison, odd-one-out)
- F: Open reasoning (LLM-judged)

### Figure 1: Accuracy vs Tool Calls
Show diminishing returns as tool calls increase (C0 → C2 → C3 → C5)

### Figure 2: Token Cost vs Accuracy Trade-off
Scatter plot demonstrating practical efficiency of tool-augmented approach

### Statistical Analysis
- McNemar's test for pairwise condition comparison
- Bonferroni correction for multiple comparisons

## Success Criteria

1. Tool-augmented (C3/C4) achieves ≥90% of full-context (C5) accuracy
2. Clear accuracy/cost trade-off curve established
3. Results statistically significant (p < 0.05)
4. Actionable deployment recommendation
