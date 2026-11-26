import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "judge_scores", Path(__file__).resolve().parents[2] / "scripts/revision/judge_scores.py")
js = importlib.util.module_from_spec(spec)
spec.loader.exec_module(js)

PANEL = ["anthropic/claude-opus-5.5", "google/gemini-4-argon", "openai/gpt-6.2-sol"]


def _w(out, judge, model, score, status="success", slot="main"):
    p = out / judge.replace("/", "__") / slot / "run1" / model.replace("/", "__") / "tool" / "F_1.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"judge_model": judge, "source": "run1", "model": model, "condition": "tool",
                             "question_id": "F_1", "status": status, "score": score}))


def test_mean_loo_and_completeness(tmp_path):
    for j, s in zip(PANEL, (2, 4, 3)):
        _w(tmp_path, j, "anthropic/claude-sonnet-4.6", s)
        _w(tmp_path, j, "qwen/qwen3.5", s)
    _w(tmp_path, PANEL[0], "openai/gpt-5.4", 5)
    _w(tmp_path, PANEL[1], "openai/gpt-5.4", None, status="api_error")
    t = js.load_scores(tmp_path, panel=PANEL)
    son = t[("run1", "anthropic/claude-sonnet-4.6", "tool", "F_1")]
    assert son["mean"] == 3 and son["score"] == 0.6 and son["loo_mean"] == 3.5 and son["complete"]
    assert t[("run1", "qwen/qwen3.5", "tool", "F_1")]["loo_mean"] == 3
    gpt = t[("run1", "openai/gpt-5.4", "tool", "F_1")]
    assert gpt["judges"] == {PANEL[0]: 5} and not gpt["complete"]


def test_repeat_slot_kept_separate(tmp_path):
    _w(tmp_path, PANEL[0], "qwen/qwen3.5", 1, slot="repeat2")
    assert js.load_scores(tmp_path, panel=PANEL) == {}
    assert js.load_scores(tmp_path, slot="repeat2", panel=PANEL)[("run1", "qwen/qwen3.5", "tool", "F_1")]["mean"] == 1
