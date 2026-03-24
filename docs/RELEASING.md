# Release Guide

## What Gets Released

| Artifact | Where | When |
|---|---|---|
| Evaluation code + graph tool | GitHub (public) | Now (already) |
| `coffee_flavor_wheel.pkl` | GitHub Release asset | On paper acceptance |
| `all_questions_system.json` | Hugging Face (gated) | On paper acceptance |
| `system_graph.pkl` | Never released | Internal only |
| Question generation scripts | Never released | Internal only |

**Rationale:** The system graph and generation scripts are internal artifacts.
Only the tool graph, question bank, and evaluation code are needed to reproduce
benchmark results against a new model.

## GitHub Release (code + tool graph)

Tag a release on paper acceptance:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Then on GitHub → Releases → New Release:
- Attach `data/graphs/coffee_flavor_wheel.pkl` as a release asset
- Write a changelog referencing the paper

## Hugging Face Dataset (question bank)

### Initial Setup (before submission)

1. Create a private HF dataset repo:
   ```bash
   pip install huggingface_hub
   huggingface-cli login
   huggingface-cli repo create flavor-bench --type dataset --private
   ```

2. Upload the question bank:
   ```python
   from huggingface_hub import HfApi
   api = HfApi()
   api.upload_file(
       path_or_fileobj="data/questions/all_questions_system.json",
       path_in_repo="all_questions_system.json",
       repo_id="<your-org>/flavor-bench",
       repo_type="dataset",
   )
   ```

3. Share with reviewers via a per-user access token — do not make public yet.

### On Acceptance

1. Add a `README.md` (dataset card) to the HF repo describing the benchmark,
   task types, and terms of use.

2. Add a `LICENSE` with terms prohibiting training use:
   ```
   This dataset is released for research and evaluation purposes only.
   Use for training machine learning models is prohibited without
   explicit written permission from the authors.
   ```

3. Enable **gated access** in HF repo settings:
   - Repo Settings → Gated → require Name, Affiliation, and agreement to terms
   - This creates a requester log and excludes the dataset from web crawlers

4. Get a DOI via Zenodo (for citation in the paper):
   - zenodo.org → New Upload → link to HF or upload snapshot directly
   - Use the DOI in the paper's data availability statement

### Loading in Code

After public release, users run the benchmark with:

```python
from datasets import load_dataset
ds = load_dataset("<your-org>/flavor-bench")
questions = ds["train"].to_list()
```

Update `BatchRunner` to accept a HF dataset path alongside a local JSON file
when this becomes the primary distribution channel.

## What Stays Private Forever

- `data/graphs/system_graph.pkl` — full 1,175-node graph used for question generation
- `scripts/` generation scripts — reveal question provenance and sampling strategy
- `data/audit_results/` — internal review history

These are already covered by `.gitignore`.
