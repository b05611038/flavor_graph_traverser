# Analysis Module

This module produces all tables, figures, and statistical results for the
paper. The core research question is simple:

> **Does giving LLMs access to a structured knowledge tool (a coffee flavor
> wheel graph) help or hurt their performance on flavor-reasoning tasks?**

The short answer is *it hurts* — on average, every model scores lower with
tool access. The analysis module exists to (a) quantify the effect with
proper statistical rigor, (b) identify the *mechanism* behind the harm, and
(c) document the exceptions where tools do help.


## Experiment at a glance

| Dimension    | Value |
|--------------|-------|
| Models       | 11 (3 closed-source, 5 thinking-token, 3 open-source) |
| Conditions   | 2 (`no_tool`, `tool`) |
| Questions    | 275 across 9 task types (A1-A5, E1-E3, F) |
| Total evals  | 6,050 (11 × 2 × 275) |
| Tool graph   | 111-node SCAA (Specialty Coffee Association) flavor wheel |
| System graph | Larger ground-truth graph used to author questions (superset of the tool graph) |
| Judge models | 3 LLM judges (Claude Opus 4.6, Gemini 3.1 Pro, GPT-5.4 Pro) for F-type rubric scoring only |


## Glossary

- **Tool graph** — the 111-node SCAA coffee flavor wheel exposed to models
  via the `validate_descriptors`, `get_parent`, `get_children`, and
  `get_siblings` tools.
- **System graph** — the larger ground-truth graph used to author questions.
  It is a *strict superset* of the tool graph. This asymmetry is the root
  cause of anchoring harm: correct answers may reference descriptors that
  exist in the system graph but not in the tool graph.
- **Macro score** — mean of per-task-type averages (equal weight per task
  type regardless of question count).
- **Micro score** — mean over all individual evaluations (weights task
  types by their question count).
- **Δ (delta)** — tool score minus no_tool score. Positive means the tool
  helped; negative means it hurt.
- **Anchoring** — models treating "not in the tool graph" as negative
  evidence and rejecting correct parametric answers, even when the
  descriptor is valid in the system graph.
- **Prompt-level anchoring** — degradation caused by the tool-condition
  system prompt alone, without the model actually calling any tool.
- **Reasoning calls** — total count of all reasoning-tool invocations in a
  single evaluation (validate_descriptors + graph-traversal tools). Used
  as a proxy for tool engagement, not a count of validate calls only.


## Scoring methods

Each question is scored in [0, 1]. Three regimes:

| Method     | Task types        | Formula |
|------------|-------------------|---------|
| Binary     | A2, A3, E1, E2, E3 | 0 if wrong, 1 if correct (single-choice) |
| F1         | A1, A4, A5         | F1 of selected options vs. ground-truth set (multi-select) |
| Judge mean | F                  | Mean of 3 LLM-judge rubric scores (0-5), normalized to [0, 1] |

All downstream analyses treat the score field as comparable across task
types. Raw 0-5 judge scores are preserved separately for inter-judge
agreement analysis.


## Quick start: reproduce all outputs

Run from the project root. Each script writes to `results/analysis/`.

```bash
# Optional: cache the full DataFrame to parquet once
python scripts/analysis/load_data.py

# Produce all paper tables, figures, and statistics
python scripts/analysis/generate_tables.py
python scripts/analysis/generate_figures.py
python scripts/analysis/statistical_tests.py
python scripts/analysis/deep_analysis.py
```


## Scripts

### `load_data.py` — Data loader

Reads all 6,050 cache JSON files into a single DataFrame. Extracts per-
evaluation metrics (tokens, latency, reasoning/validation calls), tool call
details (valid/invalid descriptor lists from `validate_descriptors`), and
individual judge scores for F-category items. Other reasoning tools
(`get_parent`, `get_children`, `get_siblings`) are counted in
`reasoning_calls` but their call arguments are not parsed.

Also provides shared constants (model groups, display names, task ordering)
and convenience aggregation functions used by all other scripts. CLI mode
saves the DataFrame to `results/analysis/all_evaluations.parquet`.

### `generate_tables.py` — Tables 1-2

**Table 1 (Leaderboard):** Macro and micro scores per model under both
conditions, grouped by model type. Answers: *how much does each model lose?*
The LaTeX caption computes the negative-Δ count dynamically, so it cannot
drift from the data.

**Table 2 (Per-category):** Score breakdown by model × task type × condition.
Answers: *where do tools help vs. hurt?* Task types A3 and E3 show positive
Δ because their questions resolve via category-level lookups where the tool
graph has good coverage; A4 and A5 show catastrophic negative Δ because
they require leaf-level validation where the tool graph has gaps. Positive
Δ cells are bolded in the LaTeX variant.

### `generate_figures.py` — Figures 1-3

**Figure 1 (Tool Δ by task type):** Bar chart with ±1 SE error bars. Green
bars = positive Δ, red bars = negative Δ. Individual model dots overlaid
with horizontal jitter; marker shape encodes model group (circle = closed-
source, square = thinking-token, triangle = open-source).

**Figure 2 (Reasoning calls vs. Δ):** Scatter of (mean reasoning_calls, Δ)
per model × task_type cell (99 points). The x-axis is `reasoning_calls`,
which counts *all* reasoning-tool invocations — not just validate calls —
so it acts as an engagement proxy. Color encodes task type. More engagement
generally means more harm, except on productive task types (A3, E3).

**Figure 3 (Per-question heatmap):** 275 × 11 heatmap of per-question Δ,
sorted by task type then mean Δ within type. Vertical bands of consistent
color indicate question-specific effects (same question hurts/helps across
models); horizontal streaks indicate model-specific effects.

### `statistical_tests.py` — Hypothesis tests

**Wilcoxon signed-rank:** Paired non-parametric test (each question is its
own control). Run per model and per task type. Reports both
Bonferroni-corrected significance (α = 0.05/11 and α = 0.05/9) and
Benjamini-Hochberg FDR-adjusted significance (α = 0.05). Rank-biserial r
is a signed effect size — positive r means the tool helped. Each row also
includes a stratified bootstrap 95% CI on mean Δ (resampling within task
type for per-model rows, within model for per-task rows).

**McNemar's test:** For binary-scored task types only (A2, A3, E1, E2, E3).
Chi-squared approximation with continuity correction. Reports N/A when
fewer than 5 discordant pairs exist. Tests whether correct↔wrong flips are
asymmetric in direction.

**Inter-judge agreement (F-category):** Krippendorff's α (interval metric),
ICC(3,k), and pairwise quadratic-weighted Cohen's κ for the 330 F-category
items (= 15 questions × 11 models × 2 conditions) scored by 3 LLM judges.
The Krippendorff implementation is simplified and assumes a fixed rater
count per item (true in this dataset).

**Bootstrap 95% CIs:** Stratified (by task type) non-parametric bootstrap
with 5,000 resamples, fixed seed, for per-model macro / micro / Δ
estimates. Uses the same equal-weight-per-task-type scheme as Table 1, so
the CIs match the point estimates reported there. Output table lets
readers see which models have intervals excluding zero — a stronger claim
than a single point estimate.

**Kruskal-Wallis (between model groups):** Non-parametric one-way ANOVA
on per-(model, question) Δ values across the three model groups
(Closed-source, Thinking-token, Open-source). Followed by pairwise
Mann-Whitney U with Bonferroni correction over the three pairs to locate
which groups differ. η² is reported as a scale-invariant effect size.

### `deep_analysis.py` — Mechanistic investigations

Goes beyond *what* happened to explain *why*:

1. **Anchoring analysis** — Spearman correlation between invalid-descriptor
   ratio and tool-condition score, per task type. Computes a Recovery
   Index (`reasoning_calls / val_call_count`) to measure whether follow-up
   graph-traversal calls mitigate anchoring. Excludes tool-condition rows
   that never called `validate_descriptors` (the exclusion count is
   printed).

2. **Prompt-level anchoring** — Zero-call subset (`reasoning_calls == 0`)
   analysis. Reports a *score drift rate* (fraction of paired items whose
   score changed by more than 0.01 between conditions). For binary tasks
   this equals the answer flip rate; for F1 / judge tasks it catches any
   score movement.

3. **Tool-skip analysis** — Compares tool-skippers vs. tool-users.
   **Caveat:** the split is observational, not randomized, so Δ gaps
   conflate selection effects with the prompt/tool effect.

4. **Token cost analysis** — Costs computed as (API-reported tokens) ×
   (OpenRouter published prices from `configs/models.yaml`). Models
   missing from the YAML are priced at $0.00 and listed in a warning
   block above the cost table.

5. **Parse error audit** — Robustness check. Recomputes every model's
   macro Δ after dropping non-success rows and verifies no Δ sign flips.


## Key findings (for paper narrative)

Each claim below points to the output file that should contain the exact
numbers — check those files rather than quoting the README verbatim.

1. **Universal negative macro Δ.** All 11 models score lower with tool
   access. See `table1_leaderboard.csv`, `macro_delta` column.

2. **Task-type split.** A3 and E3 benefit because their questions resolve
   at the category level where the tool graph has coverage. A4 is
   catastrophic because it requires leaf-level path validation where the
   tool graph has gaps. See `table2_per_category.csv` and
   `stats_wilcoxon_per_task.csv`.

3. **Anchoring is the mechanism.** `validate_descriptors` returning
   "invalid" for system-graph-only descriptors anchors models toward
   rejecting correct answers. Spearman correlations per task type are in
   `deep_anchoring_by_task.csv`.

4. **Prompt framing alone causes harm.** Zero-call subsets still show
   negative Δ for most models. See `deep_prompt_anchoring.csv`
   (`delta_zero_call` column).

5. **Cost of degradation.** Tool condition costs substantially more tokens
   per evaluation for worse results. Per-model ratios in
   `deep_token_cost.csv`.


## Output files

All written to `results/analysis/`. The **Role** column tags the claim type
each file supports so it can be slotted into the eventual paper draft:

- **Headline** — the main empirical result of the paper (tool generally
  hurts; which task types are exceptions).
- **Significance** — uncertainty quantification (CIs, p-values) that backs
  the headline claim. Typically appears as superscripts / asterisks on
  headline tables, or as a dedicated stats table.
- **Mechanism** — evidence for *why* the effect happens (anchoring from
  tool-graph coverage gaps, prompt framing alone).
- **Subgroup** — whether the effect differs across model families.
- **Reliability** — data-quality checks (judge agreement) needed to
  justify using subjective scores.
- **Robustness** — sanity checks against parsing errors, tool-skipping
  selection effects, etc.
- **Cost** — practical/economic framing of the degradation.
- **Infrastructure** — not a paper claim; cached data or bundled dumps.

| File | Role | Description |
|------|------|-------------|
| `all_evaluations.parquet` | Infrastructure | Canonical DataFrame (6,050 rows). Columns: question_id, model, condition, task_type, score, is_correct, status, reasoning/validation/token metrics, model_answer, judge_score_*, val_* aggregates |
| `table1_leaderboard.csv` / `.tex` | Headline | Model leaderboard (macro / micro / Δ by group) |
| `table2_per_category.csv` / `.tex` | Headline | Per-(model × task) no_tool / tool / Δ |
| `figure1_tool_delta_by_task.pdf` | Headline | Δ bar chart with per-model dots and group markers |
| `figure2_tool_calls_vs_delta.pdf` | Mechanism | Reasoning-call engagement vs. Δ scatter |
| `figure3_paired_heatmap.pdf` | Headline | 275 × 11 paired Δ heatmap |
| `stats_wilcoxon_per_model.csv` | Significance | Wilcoxon per model: mean Δ, bootstrap CI, W, p, p_fdr, signed rank-biserial r, Bonferroni + FDR flags |
| `stats_wilcoxon_per_task.csv` | Significance | Wilcoxon per task type (pooling models), same columns as above |
| `stats_mcnemar_per_model.csv` | Robustness | McNemar per model (binary tasks) — asymmetric-flip check complementing Wilcoxon |
| `stats_judge_agreement.json` | Reliability | Krippendorff α, ICC(3,k), pairwise κ, agreement distribution |
| `stats_bootstrap_scores.csv` | Significance | Per-model bootstrap 95% CIs on macro / micro scores and Δ (stratified by task type, 5k resamples) |
| `stats_kruskal_groups.json` | Subgroup | Kruskal-Wallis between model groups on Δ, plus pairwise Mann-Whitney post-hoc |
| `stats_all.json` | Infrastructure | Canonical dump of all stats tables combined |
| `deep_anchoring_by_task.csv` | Mechanism | Spearman(invalid_ratio, score) per task type |
| `deep_anchoring_scatter.pdf` | Mechanism | Invalid-ratio vs. score scatter |
| `deep_prompt_anchoring.csv` | Mechanism | Zero-call vs. nonzero-call Δ and score-drift rate |
| `deep_tool_skip.csv` | Robustness | Tool-skipper vs. tool-user Δ per model (observational, selection-bias caveat) |
| `deep_token_cost.csv` | Cost | Per-model mean tokens, latency, and computed cost |
| `deep_parse_errors.csv` | Robustness | Non-success cases with status and task type — verifies no Δ sign flips after dropping failures |
