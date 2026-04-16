# Experiment Cost Summary

Token consumption and cost for the completed benchmark run on OpenRouter (April 13–16, 2026).

## Experiment Parameters

- **Questions**: 275
- **Conditions**: 2 (no_tool, tool)
- **Models**: 11
- **Total evaluations**: 6,050
- **Judges**: Multi-judge panel for F-category (15 questions × 2 conditions × 11 models = 330 calls per judge)

## Per-Model Evaluation Cost

| # | Model | Provider | Input $/M | Output $/M | Tokens | Cost |
|---|-------|----------|-----------|------------|--------|------|
| 1 | Claude Sonnet 4.6 | Anthropic | $3.00 | $15.00 | 2,359K | $18.97 |
| 2 | GPT-5.4 | OpenAI | $2.50 | $15.00 | 2,359K | $18.29 |
| 3 | Gemini 3 Flash | Google | $0.50 | $3.00 | 2,359K | $3.66 |
| 4 | Grok 4.1 Fast | xAI | $0.20 | $0.50 | 2,359K | $0.77 |
| 5 | GPT-OSS 120B | OpenAI | $0.04 | $0.19 | 2,359K | $0.24 |
| 6 | Qwen3.5 397B | Alibaba | $0.39 | $2.34 | 2,359K | $2.85 |
| 7 | Kimi K2.5 | Moonshot | $0.42 | $2.20 | 2,359K | $2.75 |
| 8 | Llama 4 Maverick | Meta | $0.15 | $0.60 | 1,281K | $0.34 |
| 9 | DeepSeek V3.2 | DeepSeek | $0.26 | $0.38 | 2,359K | $0.73 |
| 10 | Mistral Medium 3.1 | Mistral | $0.40 | $2.00 | 1,281K | $1.04 |
| 11 | Nemotron 3 Super 120B | NVIDIA | $0.10 | $0.50 | 2,359K | $0.63 |
| | **Evaluation subtotal** | | | | **~24M** | **~$50.28** |

## Judge Cost

Multi-judge panel — models NOT in the tested set to avoid self-judging bias.
330 calls per judge (~1,500 input tokens + ~500 output tokens per call).

| Judge | Model ID | Input $/M | Output $/M | Cost | Status |
|-------|----------|-----------|------------|------|--------|
| Judge 1 | claude-opus-4.6 | $5.00 | $25.00 | ~$6.60 | Enabled |
| Judge 2 | gemini-3.1-pro-preview | $2.00 | $12.00 | ~$2.64 | Enabled |
| Judge 3 | gpt-5.4-pro | $30.00 | $180.00 | ~$44.55 | Optional |
| | **2-judge subtotal** | | | **~$9.24** | |
| | **3-judge subtotal** | | | **~$53.79** | |

## Total Budget

| Scenario | Evaluation | Judge | Total |
|----------|-----------|-------|-------|
| **2 judges** (Opus + Gemini Pro) | $50.28 | $9.24 | **~$59.52** |
| **3 judges** (+ GPT-5.4 Pro) | $50.28 | $53.79 | **~$104.07** |

## Multi-Judge Rationale

Using multiple judges from different providers enables:
- **Inter-judge agreement** reporting (Cohen's kappa / Krippendorff's alpha)
- **Robustness**: no single model's bias dominates F-category scores
- **Research validity**: avoids self-judging conflict (no tested model is also a judge)

Final panel: 3 judges (Opus + Gemini + GPT-5.4 Pro). GPT-5.4 Pro is the most expensive and was run as a third opinion.

## Notes

- Prices are OpenRouter rates as of April 2026.
- The two frontier models (Sonnet + GPT-5.4) account for ~65% of evaluation cost.
- Caching enabled — re-runs of already-completed questions were free.
- Re-runs were performed for kimi-k2.5 (402 payment errors, 21 files), empty responses (34 files), and nemotron token limit issue (1 file). Additional cost: ~$5.
