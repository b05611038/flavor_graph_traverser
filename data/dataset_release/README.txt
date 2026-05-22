FlavorReasonBench-Coffee
========================

A benchmark for evaluating LLM reasoning over professional coffee flavor hierarchies.

Chang, Yu-Tang & Chen, Shih-Fang (2026). Evaluating Tool-augmented Large Language
Models on Hierarchical Flavor Reasoning: FlavorReasonBench and Its First Application
to Coffee.


Files
-----
benchmark_questions.json   275 benchmark questions across 9 task types
coffee_flavor_wheel.json   111-node SCA Coffee Taster's Flavor Wheel (tool graph)


Question Format
---------------
Each question in benchmark_questions.json follows this structure:

  {
    "id":             unique question identifier,
    "task_type":      one of the 9 types listed below,
    "text":           question text shown to the model,
    "options":        dict of option letter -> option text,
    "correct_answer": string (single-select) or list of strings (multi-select),
    "answer_format":  "single_label" or "multi_label" (omitted = single_label)
  }

Fields prefixed with "_" (e.g., "_objects", "_template") are generation metadata
and should not be passed to the model.


Task Types
----------
Category A — Hierarchical structure tasks (graph traversal required):

  A1_root_classification       (n=50, multi-select)
    Which root categories does a descriptor belong to?
    Correct answer: list of option letters.
    Scoring: partial credit = fraction of correct options selected without
             penalizing unselected wrong options; strict = exact set match.

  A2_ancestor_verification     (n=50, single-select: Yes/No)
    Is descriptor X a type of descriptor Y (i.e., is Y an ancestor of X)?

  A3_sibling_identification    (n=30, single-select)
    Which option shares the same parent node as the given descriptor?

  A4_path_reconstruction       (n=30, multi-select)
    Select all option paths that are fully correct in the hierarchy.
    Correct answer: list of option letters.

  A5_lca_finding               (n=20, multi-select)
    Which options are common ancestors of two given descriptors?
    Correct answer: list of option letters.

Category E — Similarity judgment tasks (no traversal required):

  E1_similarity_ranking        (n=30, single-select)
    Select the ranking of three descriptors by similarity to a target.

  E2_pairwise_comparison       (n=30, single-select)
    Which of two options is most similar to the target descriptor?

  E3_odd_one_out               (n=20, single-select)
    Which descriptor does NOT belong with the others?

Category F — Open-ended professional reasoning:

  F_flavor_description         (n=15, free-form text)
    Professional coffee scenarios requiring flavor reasoning.
    No options field; correct_answer is absent.
    Scoring requires LLM-as-judge evaluation on a 0-5 rubric.


Flavor Wheel Graph Format
-------------------------
coffee_flavor_wheel.json contains:

  "graph_name":    name of the graph
  "root":          root node label
  "descriptions":  dict of node_label -> node description/definition
  "connections":   dict of parent_label -> list of child_labels

The graph is a directed acyclic graph (DAG). Root categories (layer 0):
  sweet, nutty/cocoa, spices, roasted, green/vegetable, fruity, floral,
  sour/fermented, other


Evaluation Notes
----------------
- For multi-select tasks (A1, A4, A5): the model must output the selected
  option letter(s). Partial credit = |correct ∩ selected| / |correct ∪ selected|
  (Jaccard). Strict = 1 only if selected set == correct set exactly.
- For single-select tasks: score is 1 if the selected option matches
  correct_answer, 0 otherwise.
- For F tasks: use LLM-as-judge with a 0-5 rubric; normalize to 0-1.
- The benchmark was evaluated under two conditions in the original study:
  no_tool (model answers from training knowledge only) and tool (model has
  access to the flavor wheel graph via API calls).


Citation
--------
If you use FlavorReasonBench-Coffee, please cite:

  Chang, Yu-Tang & Chen, Shih-Fang (2026). Evaluating Tool-augmented Large
  Language Models on Hierarchical Flavor Reasoning: FlavorReasonBench and Its
  First Application to Coffee.


License
-------
CC BY 4.0. You are free to use, share, and adapt this dataset with attribution.
