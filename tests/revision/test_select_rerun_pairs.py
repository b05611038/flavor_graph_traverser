"""Tests for scripts/revision/select_rerun_pairs.py (call extraction and classification)."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("select_rerun_pairs", ROOT / "scripts/revision/select_rerun_pairs.py")
srp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(srp)


def native(*calls):
    msgs = [{"role": "system", "content": ""}, {"role": "user", "content": "q"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": str(i), "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
                for i, (n, a) in enumerate(calls)]}]
    msgs += [{"role": "tool", "content": "{}", "tool_call_id": str(i)} for i in range(len(calls))]
    return {"conversation_history": msgs}


def icl(turns):
    """turns: list of (assistant_text, answered_with_tool_result)"""
    msgs = [{"role": "system", "content": ""}, {"role": "user", "content": "q"}]
    for text, answered in turns:
        msgs.append({"role": "assistant", "content": text})
        msgs.append({"role": "user", "content": "TOOL_RESULT: {}" if answered else "Tool access has ended."})
    return {"conversation_history": msgs}


@pytest.fixture(scope="module")
def executors(coffee_flavor_wheel_graph):
    from FlavorGraphTraverser.evaluation.tools import build_executor
    return (build_executor(coffee_flavor_wheel_graph, {"label_resolution": "exact"}),
            build_executor(coffee_flavor_wheel_graph, {"label_resolution": "resolve"}))


def test_native_extracts_all_calls():
    rec = native(("validate_descriptors", {"descriptors": ["floral"]}), ("get_parent", {"descriptor": "rose"}))
    assert list(srp.executed_calls(rec)) == [("validate_descriptors", {"descriptors": ["floral"]}),
                                            ("get_parent", {"descriptor": "rose"})]


def test_native_skips_malformed_arguments():
    rec = native(("get_parent", {"descriptor": "rose"}))
    rec["conversation_history"][2]["tool_calls"][0]["function"]["arguments"] = '{"descriptor": "ro'
    assert list(srp.executed_calls(rec)) == []


def test_icl_first_call_only_and_only_if_answered():
    t1 = ('TOOL_CALL: {"name": "get_children", "args": {"descriptor": "floral"}}\n'
          'TOOL_RESULT: {"fake": true}\nTOOL_CALL: {"name": "get_parent", "args": {"descriptor": "rose"}}')
    t2 = 'TOOL_CALL: {"name": "get_parent", "args": {"descriptor": "grapefruit"}}'
    calls = list(srp.executed_calls(icl([(t1, True), (t2, False)])))
    assert calls == [("get_children", {"descriptor": "floral"})]


def test_classify_record(executors):
    exact, resolved = executors
    rec = native(("validate_descriptors", {"descriptors": ["floral", "grapefruit", "rose"]}),
                 ("get_children", {"descriptor": "citrus fruit"}),
                 ("get_parent", {"descriptor": "jasmine"}))
    n, changed, cats = srp.classify_record(rec, exact, resolved)
    assert (n, changed) == (3, 2)
    assert cats == {"layer_label": {"floral"}, "tool_graph_misspelling": {"grapefruit"},
                    "display_correction": {"citrus fruit"}}


def test_unaffected_record(executors):
    exact, resolved = executors
    rec = native(("validate_descriptors", {"descriptors": ["rose", "blueberry jam"]}))
    assert srp.classify_record(rec, exact, resolved)[1] == 0


def test_allocate_sums_and_follows_weights():
    alloc = srp.allocate(100, {"A1": 183, "A4": 192, "E2": 15})
    assert sum(alloc.values()) == 100 and alloc["A4"] >= alloc["A1"] > alloc["E2"]


RESULTS = ROOT / "results_revision/run1/original_run.json"


@pytest.mark.skipif(not RESULTS.exists(), reason="original run results not present")
def test_golden_replay_exact_executor_matches_recorded_tool_messages(executors):
    """Exact-mode executor reproduces the tool results recorded in the April run (native path)."""
    exact, _ = executors
    records = json.load(open(RESULTS))["results"]
    checked = 0
    for r in records:
        if r["condition"] != "tool" or r["model"] == "openai/gpt-oss-20b":
            continue
        hist = r["conversation_history"]
        recorded = {m.get("tool_call_id"): m["content"] for m in hist if m.get("role") == "tool"}
        for m in hist:
            for tc in m.get("tool_calls") or []:
                content = recorded.get(tc["id"])
                if content is None or "Repeated call" in content or "budget" in content.lower():
                    continue
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                    out = exact.execute(tc["function"]["name"], args)
                except Exception:
                    continue
                assert json.loads(content) == out, (r["model"], r["question_id"], tc["function"])
                checked += 1
    assert checked > 1000
