"""Storage safety of the round launcher (scripts/revision/run_revision.py)."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "run_revision", Path(__file__).resolve().parents[2] / "scripts/revision/run_revision.py")
rr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rr)

MODELS = ["openai/gpt-5.4", "moonshotai/kimi-k2.5", "x-ai/grok-4.20"]
ROOT = Path(__file__).resolve().parents[2]
# planning reads the question set and the re-run list, which come from the data package
needs_data = pytest.mark.skipif(
    not ((ROOT / "data/questions/benchmark_questions.json").exists() and (ROOT / "results_revision/rerun_pairs.csv").exists()),
    reason="data package not present (data/questions/benchmark_questions.json, results_revision/rerun_pairs.csv)")


@needs_data
def test_plan_is_pure_and_deterministic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = rr.plan(2, MODELS, 4)
    b = rr.plan(2, MODELS, 4)
    assert rr.manifest_view(a) == rr.manifest_view(b)
    assert list(tmp_path.iterdir()) == []          # planning writes nothing


@needs_data
@pytest.mark.parametrize("run", [1, 2, 3])
def test_job_names_unique_and_parts_cover_each_job_once(run):
    jobs = rr.plan(run, rr.enabled_models(), 4)
    names = [j["name"] for j in jobs]
    assert len(names) == len(set(names))
    cover = {}
    for j in jobs:
        for q in (j["questions"] or [None]):
            key = (j["model"], j["condition"], q)
            assert key not in cover or q is None, key
            cover[key] = j["name"]


@needs_data
def test_round_totals():
    assert sum(j["n"] for j in rr.plan(1, rr.enabled_models(), 4)) == 7665
    assert sum(j["n"] for j in rr.plan(2, rr.enabled_models(), 4)) == 14080


def _fake(root, job, qid, run=2, status="success"):
    d = root / job["name"] / "cache" / job["model"] / job["condition"]
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{qid}.json").write_text(json.dumps({
        "model": job["model"], "condition": job["condition"], "question_id": qid, "status": status,
        "run_meta": {"run_tag": f"rev-run{run}-abc"}}))


def _jobs():
    return [{"name": "gpt-5.4__no_tool", "model": "openai/gpt-5.4", "condition": "no_tool", "part": None,
             "pairs": "_pairs/x.csv", "questions": ["Q1", "Q2"], "n": 2}]


def test_merge_reads_caches_and_writes_all(tmp_path):
    jobs = _jobs()
    for q in ("Q1", "Q2"):
        _fake(tmp_path, jobs[0], q)
    (tmp_path / jobs[0]["name"] / "results.json").write_text('{"results": []}')   # emptied by a crash
    assert rr.merge(tmp_path, jobs, 2) == 0
    assert len(json.loads((tmp_path / "merged_results.json").read_text())["results"]) == 2


def test_merge_refuses_incomplete_duplicate_and_foreign_round(tmp_path):
    jobs = _jobs()
    _fake(tmp_path, jobs[0], "Q1")
    assert rr.merge(tmp_path, jobs, 2) == 1                                   # Q2 missing
    _fake(tmp_path, jobs[0], "Q2", status="api_error")
    assert rr.merge(tmp_path, jobs, 2) == 1                                   # api_error counts as a gap
    _fake(tmp_path, jobs[0], "Q2", run=1)
    assert rr.merge(tmp_path, jobs, 2) == 1                                   # tagged as another round
    twin = dict(jobs[0], name="gpt-5.4__no_tool__part2", part=2)
    _fake(tmp_path, jobs[0], "Q2")
    _fake(tmp_path, twin, "Q2")
    assert rr.merge(tmp_path, jobs + [twin], 2) == 1                          # duplicate across parts
    assert not (tmp_path / "merged_results.json").exists()


def test_root_must_belong_to_its_round(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["run_revision.py", "--run", "2", "--root", "results_revision/run1", "--dry-run"])
    assert rr.main() == 1
    assert "must be results_revision/run2" in capsys.readouterr().out


def test_is_api_error_detects_hidden_errors():
    assert rr.is_api_error({"status": "api_error"})
    assert rr.is_api_error({"status": "parse_error", "errors": [{"type": "api_error"}]})
    assert rr.is_api_error({"status": "no_judge", "errors": [{"type": "api_error"}]})
    assert not rr.is_api_error({"status": "success", "errors": [{"type": "tool_error"}]})
    assert not rr.is_api_error({"status": "success"})
