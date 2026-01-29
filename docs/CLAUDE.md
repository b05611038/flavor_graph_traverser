# CLAUDE.md

## Project Goal

Benchmark tool-augmented LLM inference on coffee flavor hierarchy reasoning. Compare against direct prompting and full-context baselines.

## Benchmark Construction Methodology

### Graph Setup

This benchmark uses two coffee flavor hierarchy graphs with an **asymmetric design** to test tool-augmented reasoning:

#### SYSTEM Graph (Question Generation)
- **Source**: Internal comprehensive flavor ontology (not publicly available)
- **Scale**: 1,175 flavor descriptions, 1,824 hierarchical connections
- **Depth**: Multi-level taxonomy (root → category → subcategory → specific flavors)
- **Purpose**: Generate diverse, high-quality benchmark questions
- **Filtering**: Applied hierarchical filtering pipeline to select 892 valid nodes (75.9%)
  - Excluded abstract concepts (e.g., "taste", "overall")
  - Excluded defect categories
  - Required minimum depth (≥2) to target specific flavors
  - Manual exception lists (blacklist/whitelist) for quality control
  - See `docs/CONFIG.md` and `docs/FILTERING_WORKFLOW.md` for details

#### coffee_flavor_wheel Graph (Tool for LLMs)
- **Source**: Simplified public flavor wheel
- **Scale**: 111 flavor descriptions, 110 connections
- **Purpose**: Provided as a graph traversal tool to LLMs during inference
- **Coverage**: Subset of SYSTEM graph, representing commonly recognized flavors

### Rationale for Asymmetric Design

The SYSTEM-to-coffee_flavor_wheel setup creates a realistic scenario:

1. **Questions are comprehensive**: Generated from SYSTEM's broad coverage (892 filtered nodes)
2. **Tool access is limited**: LLMs query the smaller coffee_flavor_wheel (111 nodes)
3. **Tests reasoning under uncertainty**:
   - Some questions reference nodes in SYSTEM but not in coffee_flavor_wheel
   - LLMs must use tool strategically (traverse, infer, reason from partial information)
   - Mirrors real-world scenarios where tools provide incomplete domain knowledge

4. **Evaluation conditions**:
   - **C0-C2**: Direct prompting with varying context
   - **C3-C4**: Tool-augmented inference (coffee_flavor_wheel access)
   - **C5**: Full-context baseline (entire SYSTEM graph provided)

### Reproducibility Note

While `SYSTEM.pkl` is derived from internal data and not included in public releases, this documentation preserves the methodology:
- Filtering rules and parameters are documented (`docs/CONFIG.md`)
- Question generation logic is fully reproducible (`scripts/generate_questions.py`)
- The filtered node set can be regenerated from alternative comprehensive flavor ontologies
- The benchmark questions (`data/questions/*.json`) are included in releases

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
