import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "run_judges", Path(__file__).resolve().parents[2] / "scripts/revision/run_judges.py")
rj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rj)


def _rec(model, cond, qid, text="answer", status="no_judge", errors=None, tag="rev-run1-x"):
    return {"model": model, "condition": cond, "question_id": qid, "model_response_text": text,
            "status": status, "errors": errors or [], "run_meta": {"run_tag": tag}}


def _write(root, rel, rec):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec))


def test_collect_skips_cut_off_and_empty_and_reads_april_read_only(tmp_path):
    _write(tmp_path, "results_revision/run1/j/cache/a/m/no_tool/F_1.json", _rec("a/m", "no_tool", "F_1"))
    _write(tmp_path, "results_revision/run1/j/cache/a/m/no_tool/F_2.json",
           _rec("a/m", "no_tool", "F_2", errors=[{"type": "api_error"}]))
    _write(tmp_path, "results_revision/run1/j/cache/a/m/no_tool/F_3.json", _rec("a/m", "no_tool", "F_3", text=" "))
    _write(tmp_path, "results_revision/run2/j/cache/a/m/no_tool/F_1.json",
           _rec("a/m", "no_tool", "F_1", tag="rev-run2-x"))
    april = {"results": [_rec("a/m", "tool", "F_1"), _rec("z/gone", "tool", "F_1"), _rec("a/m", "tool", "A1_1")]}
    (tmp_path / "results_revision/run1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "results_revision/run1/original_run.json").write_text(json.dumps(april))
    before = (tmp_path / "results_revision/run1/original_run.json").read_text()
    got = rj.collect_answers(tmp_path, april_models=("a/m",), april_expected=None)
    keys = sorted((a["source"], a["condition"], a["question_id"]) for a in got)
    assert keys == [("april", "tool", "F_1"), ("run1", "no_tool", "F_1"), ("run2", "no_tool", "F_1")]
    assert (tmp_path / "results_revision/run1/original_run.json").read_text() == before


def test_collect_refuses_foreign_run_tag(tmp_path):
    _write(tmp_path, "results_revision/run2/j/cache/a/m/no_tool/F_1.json", _rec("a/m", "no_tool", "F_1"))
    (tmp_path / "results_revision/run1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "results_revision/run1/original_run.json").write_text('{"results": []}')
    import pytest
    with pytest.raises(SystemExit):
        rj.collect_answers(tmp_path, april_models=(), april_expected=None)


def test_out_path_separates_judge_slot_source():
    a = {"source": "run2", "model": "a/m", "condition": "tool_rerun", "question_id": "F_1"}
    p = rj.out_path("OUT", "openai/gpt-6.2-sol", "repeat2", a)
    assert p == Path("OUT/openai__gpt-6.2-sol/repeat2/run2/a__m/tool_rerun/F_1.json")
    assert rj.out_path("OUT", "openai/gpt-6.2-sol", "main", a) != p


def test_sample_is_seeded_and_order_independent():
    ans = [{"source": "run1", "model": "m", "condition": "c", "question_id": f"F_{i}"} for i in range(50)]
    s1 = rj.sample(ans, 10)
    s2 = rj.sample(list(reversed(ans)), 10)
    assert s1 == s2 and len(s1) == 10


def test_judges_are_the_configured_panel():
    assert [j["id"] for j in rj.load_judges()] == [
        "anthropic/claude-opus-5.5", "google/gemini-4-argon", "openai/gpt-6.2-sol"]


class _Resp:
    def __init__(self, content, finish="stop", served="openai/gpt-6.2-sol"):
        self.content, self.finish_reason, self.resolved_model = content, finish, served
        self.thinking_content, self.provider = None, "P"

        class U:
            input_tokens, output_tokens = 100, 50
        self.usage = U()


class _Client:
    def __init__(self, resps):
        self.resps, self.calls = list(resps), []

    def query(self, messages, temperature=None, max_tokens=None):
        self.calls.append(temperature)
        return self.resps.pop(0)


J = {"id": "openai/gpt-6.2-sol", "name": "Sol", "provider": "openai", "temperature": None,
     "pricing": {"input": 2.0, "output": 10.0}}
Q = {"id": "F_1", "text": "Q?", "evaluation": {"judging_notes": {}}}
A = {"source": "run2", "model": "a/m", "condition": "no_tool", "question_id": "F_1", "response": "answer"}


def test_truncated_or_wrong_model_is_retryable_not_final(tmp_path):
    p = tmp_path / "r.json"
    for resp in (_Resp("mentions 3 origins and 2 roast lev", finish="length"), _Resp("", finish="stop"),
                 _Resp("Score: 4", served="openai/gpt-6.2-astra")):
        rec = rj.judge_one(_Client([resp]), J, Q, A, p, "c")
        assert rec["status"] == "api_error" and rec["score"] is None
        assert not rj.is_final(p, rj.sha("answer"))


def test_success_final_only_for_same_answer_and_usage_accumulates(tmp_path):
    p = tmp_path / "r.json"
    rj.judge_one(_Client([_Resp("x", finish="error")]), J, Q, A, p, "c")
    rec = rj.judge_one(_Client([_Resp("Good.\nScore: 4", served="openai/gpt-6.2-sol-20261118")]), J, Q, A, p, "c")
    assert rec["status"] == "success" and rec["score"] == 4
    assert rec["usage_total"] == {"input_tokens": 200, "output_tokens": 100}
    assert rj.is_final(p, rj.sha("answer"))
    assert not rj.is_final(p, rj.sha("a changed answer"))


def test_temperature_follows_judge_config(tmp_path):
    c = _Client([_Resp("Score: 3")])
    rec = rj.judge_one(c, J, Q, A, tmp_path / "r.json", "c")
    assert c.calls == [None] and rec["request"]["temperature_sent"] is False
    c = _Client([_Resp("Score: 3", served="google/gemini-4-argon")])
    rj.judge_one(c, dict(J, id="google/gemini-4-argon", temperature=0.0), Q, A, tmp_path / "s.json", "c")
    assert c.calls == [0.0]


def test_openrouter_client_omits_temperature_none(monkeypatch):
    from FlavorGraphTraverser.evaluation.client.openrouter import OpenRouterClient
    from FlavorGraphTraverser.evaluation.client.base import Message
    sent = []
    monkeypatch.setattr(OpenRouterClient, "_make_request", lambda self, payload: sent.append(payload) or "ok")
    c = OpenRouterClient(model="x/y", api_key="k")
    c.query([Message(role="user", content="hi")], temperature=None)
    c.query([Message(role="user", content="hi")], temperature=0.0)
    assert "temperature" not in sent[0] and sent[1]["temperature"] == 0.0


def test_frozen_sample_reused(tmp_path):
    ans = [{"source": "run1", "model": "m", "condition": "c", "question_id": f"F_{i}", "response": "r"} for i in range(30)]
    f = tmp_path / "s.json"
    s1 = rj.frozen_sample(ans, 5, f)
    s2 = rj.frozen_sample(ans + [{"source": "run3", "model": "m", "condition": "c", "question_id": "F_99", "response": "r"}], 5, f)
    assert [rj.akey(a) for a in s1] == [rj.akey(a) for a in s2]


def test_last_digit_fallback_is_retried_not_trusted(tmp_path):
    c = _Client([_Resp("<end_of_image> 3 <end_of_image>"), _Resp("fine.\nScore: 4")])
    rec = rj.judge_one(c, J, Q, A, tmp_path / "r.json", "c")
    assert rec["status"] == "success" and rec["score"] == 4 and len(rec["attempts"]) == 2
    c = _Client([_Resp("junk 2")] * 3)
    rec = rj.judge_one(c, J, Q, A, tmp_path / "s.json", "c")
    assert rec["status"] == "parse_error" and rec["score"] is None
