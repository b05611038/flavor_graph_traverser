# flavor_graph_traverser

> Evaluating Tool-Augmented LLMs for Hierarchical Sensory Reasoning

## Research Question

For domain-specific hierarchical reasoning, how does tool-augmented inference compare to direct prompting and full-context approaches?

## Thesis

Tool-augmented LLMs achieve near-full-context accuracy with significantly lower token cost, making them practical for deployable sensory recommendation systems.

## Benchmark

- **275 questions** across taxonomic reasoning, similarity reasoning, and open reasoning tasks
- **6 experimental conditions** (C0-C5): zero-shot, CoT, tool-augmented (1-3 calls), full-context
- **5 models** evaluated via OpenRouter API
- **Domain**: Coffee flavor hierarchy (SCA Flavor Wheel, ~110 descriptors)

## Expected Outputs

1. Accuracy comparison table: Model × Condition
2. Per-task breakdown: which tasks benefit most from tools
3. Accuracy vs. token cost trade-off analysis
4. Statistical significance tests (McNemar's test)
5. Deployment recommendations for sensory recommendation systems

## Related Work

Part of the IR-BERT Coffee Chat System project.
