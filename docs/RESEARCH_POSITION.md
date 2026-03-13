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

## F Question Structure: Three Scenario Groups

F questions are organized into 3 groups of 5 questions each (15 total). Each group shares a common reasoning structure, which reduces evaluation variance — the judge assesses 5 questions within a consistent scenario type rather than across unrelated contexts.

The three groups are chosen to be structurally distinct: different user types, different reasoning directions, and different roles for the flavor hierarchy.

---

### Group 1: Communication / Translation (5 questions)

**Context:** Coffee shop interactions between baristas and customers.

**Reasoning structure:** Bidirectional translation between everyday informal language and the flavor hierarchy's technical vocabulary, at the appropriate level of specificity for the audience.

**What this tests:** Whether the LLM can parse a customer's vague or cross-domain flavor expression (e.g., "something bright, not too bitter, like juice") into hierarchy-grounded descriptors — and conversely, explain a coffee's technical tasting notes in language a non-expert understands.

**Why this is distinct:** The goal is not to make a recommendation or design a product. It is to communicate accurately across a vocabulary gap. The hierarchy determines what is accurate; the LLM determines what is accessible.

**Example scenario direction:**
> A customer says they enjoy "something that tastes like fruit tea — sweet but with a little edge." A barista needs to identify which region of the flavor wheel matches this description, and recommend a coffee using that vocabulary.

---

### Group 2: Preference-to-Product (5 questions)

**Context:** A customer or buyer wants a specific flavor experience. The task is to navigate from that expressed preference through the hierarchy to a concrete recommendation or blend.

**Reasoning structure:** Forward search — from a target flavor (possibly expressed in cross-domain terms) → locate it in the hierarchy → find available descriptors or combinations that approximate it → produce a reasoned recommendation.

**What this tests:** Whether the LLM can use graph proximity and branch structure to find valid approximations when the exact target is unavailable, rather than improvising from intuition.

**Why this is distinct:** The reasoning is constrained by availability (what coffees or descriptors exist) and requires graph traversal to find the closest valid path. Creative suggestions that bypass the hierarchy are the failure mode being tested against.

**Example scenario direction:**
> A customer wants a blend that evokes blueberry. No single-origin coffee in stock has an explicit blueberry descriptor. Using the flavor wheel, identify which available descriptors are closest in the hierarchy and could combine to approximate the target.

---

### Group 3: Production Factors → Flavor Outcomes (5 questions)

**Context:** Coffee producers, roasters, and Q-graders reasoning about how upstream production decisions shape flavor outcomes.

**Reasoning structure:** Causal reasoning from production variables (fermentation type/duration, roast profile) through the hierarchy to predicted or observed flavor positions — both forward (process → expected flavor shift) and diagnostic (unexpected flavor → likely production cause).

**What this tests:** Whether the LLM can connect industry-standard production knowledge to specific positions in the flavor hierarchy, rather than giving vague associations ("natural process coffees are more fruity"). The hierarchy makes the reasoning precise and verifiable.

**Why this is distinct:** The reasoning direction is bottom-up from raw material and process, not top-down from preference. The user type is a producer or roaster, not a consumer. The graph is used as a structured knowledge base about process-flavor relationships, not a recommendation engine.

**Scope:** Fermentation (duration, aerobic/anaerobic/carbonic maceration, degree of fermentation) and roasting (roast level, development time ratio, roast curve shape) are the two production variables in scope. Varietal and terroir are excluded — their flavor effects are less systematically codified in the flavor wheel and harder to judge fairly.

**Example scenario direction:**
> A roaster extended the fermentation time on a natural-process lot and noticed an unexpected shift in the cup. Based on the flavor wheel, which branch is this shift most likely moving toward, and at what point does it cross from a positive characteristic into a defect signal?

---

## Broader Implications

The same design principle applies beyond coffee. Any domain with a codified, hierarchical standard — wine (sommelier wheel), beer (BJCP flavor guide), tea, perfumery — could benefit from this benchmark paradigm. The flavor hierarchy is a general instrument; the system is designed to be extensible to new domains by adding new graphs.

The central research claim is:

> For domain-specific hierarchical flavor reasoning, tool-augmented LLMs that follow the professional standard outperform unaugmented LLMs that rely on training intuition — and the gap is largest on decision-making tasks that require graph traversal, not simple lookup.

---

*Written: 2026-03-13. Based on design discussions during benchmark development.*
