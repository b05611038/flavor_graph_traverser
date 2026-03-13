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
| C0 (no tools) | Answers from training intuition — may sound plausible but be graph-inconsistent |
| C3/C4 (flavor wheel tool) | Traverses the tool graph to find adjacent nodes — reasoning grounded in hierarchy |
| C5 (full system graph) | Reasons with maximum graph coverage — most precise proximity reasoning |
| Judge (system graph tool) | Verifies whether reasoning direction matches the full hierarchy |

The gap between C0 and C3/C4 measures the **value of following the guide** over relying on training intuition. The gap between C3/C4 and C5 measures the **cost of the tool's incompleteness** (the flavor wheel has 111 nodes; the system graph has 1,175).

---

## Broader Implications

The same design principle applies beyond coffee. Any domain with a codified, hierarchical standard — wine (sommelier wheel), beer (BJCP flavor guide), tea, perfumery — could benefit from this benchmark paradigm. The flavor hierarchy is a general instrument; the system is designed to be extensible to new domains by adding new graphs.

The central research claim is:

> For domain-specific hierarchical flavor reasoning, tool-augmented LLMs that follow the professional standard outperform unaugmented LLMs that rely on training intuition — and the gap is largest on decision-making tasks that require graph traversal, not simple lookup.

---

*Written: 2026-03-13. Based on design discussions during benchmark development.*
