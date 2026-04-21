# Documentation

How to execute and reproduce the FlavorGraphTraverser benchmark.

## Guides

| File | Purpose |
|---|---|
| [QUESTION_GENERATION.md](QUESTION_GENERATION.md) | Generate benchmark questions from the flavor graph |
| [AUDITING.md](AUDITING.md) | Audit and review generated questions |
| [TESTING.md](TESTING.md) | Run the test suite |
| [RELEASING.md](RELEASING.md) | Release checklist and current status |
| [COST.md](COST.md) | Token consumption and cost for the benchmark run |

## Implementation Records

Incident and decision logs from the benchmark run in [`memos/`](memos/):

| File | Summary |
|---|---|
| [memo_cutoff_bug_20260415.md](memos/memo_cutoff_bug_20260415.md) | Premature tool-loop exit bug — affected 11.1% of tool-condition cache entries |
| [memo_parse_errors_20260415.md](memos/memo_parse_errors_20260415.md) | Parse error tracking — 70 initial non-success files, resolved to 20 accepted as model behavior |
