# Research Position and Benchmark Design Philosophy

This document captures the design rationale behind the benchmark, particularly the F (open-ended reasoning) task type. It is intended as a reference when writing the paper's introduction, motivation, and methodology sections.

---

## Why This Benchmark Exists

Flavor perception is inherently personal. People do not share identical sensory systems — no two people smell or taste in exactly the same way. This means flavor assessment in daily life cannot be fully standardized, and any system claiming to replicate individual perception from text data alone is making an unjustifiable claim.

However, professional domains have developed **codified, intersubjective standards** — the most prominent being the Specialty Coffee Association's Coffee Flavor Wheel. These standards represent collective agreement among experts: a shared vocabulary and hierarchy that allows professionals to communicate about flavor consistently, regardless of individual variation. The flavor wheel is not a map of one person's sensory experience; it is a socially constructed, field-accepted reference frame.

This distinction is the foundation of the benchmark:

> **LLMs cannot sense. Their legitimate role is to reason faithfully within a codified professional standard — not to substitute for perception or to improvise beyond the guide.**

---

## The Role of LLMs in Flavor Reasoning

LLMs acquire flavor-related knowledge from pre-training corpora (reviews, tasting notes, manuals, etc.). This gives them some exposure to flavor vocabulary and associations. However:

1. **They cannot perceive.** No amount of text exposure creates genuine olfactory or gustatory experience.
2. **They cannot personalize.** Flavor preference is tied to individual neural and cultural experience, which cannot be transferred through text.
3. **They can follow a guide.** A codified hierarchy like the flavor wheel is a linguistic and structural artifact — exactly the kind of knowledge that can be learned from text and applied through reasoning.

The practical implication: an LLM that applies the flavor wheel correctly to a decision is genuinely useful. An LLM that deviates from the flavor wheel — inventing substitutions or associations from training intuition — is producing unverifiable speculation, adding noise rather than value. Real-world sensory complexity is far beyond what text-trained models can track; the flavor wheel is a deliberate simplification that makes the problem tractable.

This is why the benchmark tests **tool-augmented reasoning against the flavor hierarchy**, not flavor knowledge in the abstract.

---

## Why the Hierarchy Enables Real Decisions

The flavor wheel is not just a reference for answering questions — it is a **decision-making instrument**. In daily life, people use flavor knowledge to:

- Select ingredients for blending or pairing
- Substitute unavailable flavors with adjacent alternatives
- Communicate preferences across domain boundaries (e.g., "I like lychee — what coffee should I try?")
- Identify whether a perceived note is a quality characteristic or a defect
- Build tasting notes that can be understood by others

These are decisions that benefit from graph traversal: finding nodes close to a target, identifying which branch a descriptor belongs to, understanding when two flavors share a common ancestor, and knowing when a note signals quality versus defect.

Simple lookup of the flavor wheel is insufficient for these tasks — they require reasoning across the structure of the hierarchy. This is the capability the benchmark is designed to measure.

---

## The Coffee Blending Example

A concrete illustration of the intended task class:

> A user wants to blend five single-origin coffees to produce a cup with a blueberry note. None of the available coffees has an explicit blueberry descriptor. Which coffees should be combined, and why?

A correct reasoning process:
1. Locate "blueberry" in the hierarchy: blueberry → berry → fruity
2. Find available descriptors that are siblings or near-neighbors of blueberry in the berry branch
3. Reason that combining berry-adjacent flavors (e.g., strawberry, red currant) may approximate the target perception
4. Ground the recommendation in the hierarchy, not in intuition

An LLM that does this — using the flavor wheel tool — is applying the guide correctly. An LLM that suggests "passion fruit, because it's also bright and tropical" is improvising outside the hierarchy. Even if the latter sounds plausible, it is epistemically ungrounded relative to the professional standard.

This class of question cannot be answered by lookup alone, cannot be machine-verified by exact node matching (the reasoning may use adjacent vocabulary), and has a clear criterion for quality: does the answer stay within and follow the logic of the hierarchy?

---

## Why F Questions Cannot Be Machine-Verified

Open-ended reasoning tasks in this benchmark should not be evaluated by matching output tokens to graph nodes. Reasons:

1. **Vocabulary openness.** A model may correctly reason toward a berry-family substitution while using words not in the system graph. Penalizing this introduces vocabulary bias, not reasoning quality assessment.
2. **Sensory communication is not binary.** There is no single correct answer to "what should I blend to approximate blueberry?" — there are better and worse answers, grounded or ungrounded in the hierarchy.
3. **The standard is directional, not exact.** The flavor wheel encodes proximity and hierarchy; correctness means following that direction, not naming specific nodes.

---

## Evaluation Design for F Questions

**Judge model:** An LLM with access to the system graph (the larger, cleaned graph used for question generation) as a tool.

**Judge task:** Assess whether the test model's reasoning follows the logic of the hierarchy — not whether it names specific nodes.

Concretely, the judge:
1. Reads the test model's answer
2. Uses system graph tool calls to verify whether the reasoning is graph-consistent (are the suggested nodes/branches actually close to the target in the hierarchy?)
3. Assesses whether the reasoning *direction* is correct — did the model go to the right part of the hierarchy, even if using different words?
4. Flags answers that deviate from the guide without justification

**What the judge does not do:**
- Check for exact node name matches
- Penalize valid reasoning expressed in vocabulary outside the graph
- Evaluate personal opinion or sensory claims

This design is internally consistent with the benchmark's experimental conditions: the judge itself is a demonstration of tool-augmented reasoning, using the system graph to evaluate whether the test model used the smaller flavor wheel tool appropriately.

---

## Experimental Signal from F Questions

| Condition | Expected behavior |
|---|---|
| no_tool | Answers from training intuition — may sound plausible but be graph-inconsistent |
| tool (flavor wheel) | Traverses the tool graph to find adjacent nodes — reasoning grounded in hierarchy |
| Judge (system graph tool) | Verifies whether reasoning direction matches the full hierarchy |

The gap between `no_tool` and `tool` measures the **value of following the guide** over relying on training intuition.

---

## F Question Structure: Three Scenario Groups

F questions are organized into 3 groups of 5 questions each (15 total). Each group shares a common reasoning structure, which reduces evaluation variance — the judge assesses 5 questions within a consistent scenario type rather than across unrelated contexts.

The three groups are chosen to be structurally distinct: different user types, different reasoning directions, and different roles for the flavor hierarchy.

All F questions use open-ended format, evaluated by LLM judge (0-5 scoring). Judging notes include branch reference mappings, what to evaluate, and scoring rubrics that assess reasoning quality rather than specific conclusions.

---

### Group 1: Communication / Translation (5 questions)

**Context:** Coffee shop interactions between baristas and customers.

**Reasoning structure:** Bidirectional translation between everyday informal language and the flavor hierarchy's technical vocabulary, at the appropriate level of specificity for the audience.

**What this tests:** Whether the LLM can parse a customer's vague or cross-domain flavor expression (e.g., "something bright, not too bitter, like juice") into hierarchy-grounded descriptors — and conversely, explain a coffee's technical tasting notes in language a non-expert understands.

**Why this is distinct:** The goal is not to make a recommendation or design a product. It is to communicate accurately across a vocabulary gap. The hierarchy determines what is accurate; the LLM determines what is accessible.

**Questions:** F_g1_q1 through F_g1_q5 (communication scenarios).

---

### Group 2: Professional Decision-Making (5 questions)

**Context:** Coffee professionals (roasters, buyers, café managers) making decisions that require flavor hierarchy reasoning — sourcing, blending, menu design, and quality control.

**Reasoning structure:** Multi-step reasoning combining informal flavor language, cupping data, and practical constraints (volume, price, relationships) with branch-level analysis from the flavor hierarchy.

**What this tests:** Whether the LLM can connect buyer/owner requests (often in informal language) to specific hierarchy positions, then make decisions grounded in branch reasoning rather than surface-level word matching.

**Why this is distinct:** Decisions have real-world consequences (business relationships, product quality). The LLM must balance flavor reasoning with practical constraints. No single correct answer — reasoning quality is what matters.

**Questions:**

| ID | Scenario | Key reasoning challenge |
|---|---|---|
| F_g2_q1_sourcing | Green coffee sourcing | Origin characteristics → hierarchy positioning |
| F_g2_q2_blend_or_single | Blend vs. single-origin decision | Customer preference → product recommendation |
| F_g2_q3_blend_evaluation | Blend quality evaluation | Cupping notes → branch analysis → quality assessment |
| F_g2_q4_blend_design | Espresso blend design | Ambiguous components, no clean rejects, ratio reasoning. Target described without naming specific correct coffees. Rubric evaluates reasoning quality, not specific blend recipe. |
| F_g2_q5_menu_curation | Café menu correction | Bottle matching (smell vs. menu, zero word overlap) + cross-branch mismatch detection (Kenya menu says sweet/berry, actual is citrus-dominant). Open-ended: "The café opens in an hour. What needs to be sorted out?" |

---

### Group 3: Production Factors → Flavor Outcomes (5 questions)

**Context:** Coffee producers, roasters, and processing station managers reasoning about how upstream production decisions shape flavor outcomes.

**Reasoning structure:** Causal reasoning from production variables (roast profile, fermentation duration, processing method, drying conditions) through the hierarchy to predicted or observed flavor positions — both forward (process → expected flavor shift) and diagnostic (unexpected flavor → likely production cause).

**What this tests:** Whether the LLM can connect production knowledge to specific positions in the flavor hierarchy, rather than giving vague associations ("natural process coffees are more fruity"). The hierarchy makes the reasoning precise and verifiable.

**Why this is distinct:** The reasoning direction is bottom-up from raw material and process, not top-down from preference. The user type is a producer or roaster, not a consumer. The graph is used as a structured knowledge base about process-flavor relationships, not a recommendation engine.

**Scope:** Roasting (roast level, development time, rate of rise) and processing (fermentation duration, honey process levels, natural process, drying method) are the production variables in scope. Varietal and terroir are excluded — their flavor effects are less systematically codified in the flavor wheel and harder to judge fairly.

**Design principles:**
- Cupping descriptors never word-match reference tables — branch reasoning required
- Processing/roast reference tables describe physical processes and general tendencies, not flavor outcomes
- Buyer/owner language is indirect, requiring branch mapping to interpret
- No single correct answer — scoring evaluates reasoning quality
- Multiple valid approaches accepted if supported by branch reasoning

**Questions:**

| ID | Scenario | Key reasoning challenge |
|---|---|---|
| F_g3_q1_roast_defect | Roast defect diagnosis | Cupping notes → branch mapping → defect table (no adjustment column) → roast log analysis. Dual defect: underdeveloped (peapod/straw → green/vegetable) + baked (wheat → roasted/cereal, temperature stalled 196→197°C). Must propose executable adjustment. |
| F_g3_q2_roast_comparison | Roast profile comparison | Two profiles (fast vs. slow) of same Peru lot. Owner says "lychee thing" — must map to apricot + chamomile through branches. Speed vs. endpoint as independent variables. Honest trade-off communication. |
| F_g3_q3_fermentation_selection | Fermentation batch allocation | Four SIAF batches (0h, 24h, 48h, 72h) with distinct branch profiles. Two buyers use indirect flavor language ("warm, toasty depth" / "smoky-sweet, aged"). Both converge on Batch C. Volume + price + relationship tension. |
| F_g3_q4_processing_track | Processing track decision | Rwanda washing station, 5 farmers' lots with cherry quality data + cupping history. 800 kg capacity constraint. Buyer wants "floral/juicy + more body and sweetness." Must predict blended product profiles, handle new farmer (no history), consider processing upgrade for borderline lot. |
| F_g3_q5_honey_process | Processing method design | Costa Rica micro-mill with cupping records for washed, white honey, yellow honey, natural 24h, natural 48h. Reference table for all methods (physical description, general tendency — no flavor specifics). Buyer wants "peach compote not berry smoothie." Natural trap: natural has most fruit intensity but wrong sub-branch (berry, not stone fruit). Must extrapolate honey trajectory (citrus → stone fruit) and distinguish sub-branches. |

---

## Broader Implications

The same design principle applies beyond coffee. Any domain with a codified, hierarchical standard — wine (sommelier wheel), beer (BJCP flavor guide), tea, perfumery — could benefit from this benchmark paradigm. The flavor hierarchy is a general instrument; the system is designed to be extensible to new domains by adding new graphs.

The central research claim is:

> Structured domain knowledge bases (such as the SCAA Coffee Flavor Wheel) can provide benefit for LLMs on taxonomy-grounded queries — but only when the KB vocabulary covers the query terms. When questions use real-world descriptors that fall outside the KB's vocabulary (as they do in practice), partial KB coverage creates **anchoring harm**: models treat "not found in graph" as negative evidence, abandoning correct knowledge-based reasoning in favor of incomplete tool output. This effect was observed across all 11 models tested, producing universally negative tool Δ on both taxonomy and similarity task types.

This is a practically useful finding for anyone deploying KB-augmented LLMs in food production, quality control, or sensory evaluation: the gap between a formal standard's vocabulary and real-world language is not merely a coverage limitation — it is an active source of reasoning degradation. Tool-augmented systems must be designed to handle vocabulary mismatch explicitly, not merely to provide lookup access.

---

## Empirical Findings (April 2026)

The completed experiment (6,050 evaluations across 11 models) produced a clear and consistent result: **every model performed worse with tool access than without**. Macro score Δ ranged from -0.020 (nemotron) to -0.142 (mistral).

This contradicts the initial hypothesis that tools would help on taxonomy tasks (A1–A3) while providing no benefit on similarity tasks (E). In practice, even taxonomy tasks showed negative Δ for most models. The root cause is the asymmetric graph design: questions are generated from 1,175 nodes, but the tool graph contains only 111. When models validate descriptors and find them absent, they anchor on this absence rather than reasoning from their own knowledge.

The anchoring effect is strongest for models that make more tool calls (mistral, gpt-oss) and weakest for models that tend to answer directly despite having tool access (nemotron, kimi). This suggests that the harm is proportional to tool engagement, not model capability.

---

## Prompt Optimization Notes (Tool Condition)

The tool condition system prompt was empirically optimized through a 5-version ablation (v3–v7) on GPT-OSS-20B before the full multi-model run. The key finding:

**The validated v3 prompt** warns against partial-match inference ("finding 'blueberry' does not tell you where 'blueberry jam' sits") without prescribing a per-question-type strategy. More prescriptive prompts (v5–v7) increased tool call volume for question types where graph data is misleading, producing net regressions.

The fundamental constraint: the model cannot be reliably instructed (via system prompt alone) to skip tools for specific question types. Partial graph information — even a single validate call returning all-invalid — can anchor the model away from a better knowledge-based answer. This anchoring effect is an observed failure mode worth reporting, not an artifact of poor prompting.

---

*Written: 2026-03-13. Updated: 2026-04-16. Broader Implications updated with empirical findings from completed experiment (6,050 evaluations, 11 models). Prompt Optimization Notes from v3–v7 ablation study.*
