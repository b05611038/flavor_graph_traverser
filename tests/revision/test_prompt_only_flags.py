"""Flags for responses in the tool-prompt-without-tools control (prompt_only_flags.classify)."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "prompt_only_flags", Path(__file__).resolve().parents[2] / "scripts/revision/prompt_only_flags.py")
flags = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flags)


def rec(text, status="success", answer="A", thinking=""):
    return {"condition": "prompt_only", "model": "m", "question_id": "A2_x", "status": status,
            "model_answer": answer,
            "conversation_history": [{"role": "assistant", "content": text, "thinking_content": thinking}]}


@pytest.mark.parametrize("text,kind", [
    ('TOOL_CALL: {"name": "get_parent", "args": {"descriptor": "rose"}}', "simulated_call"),
    ("Let me call get_parent on 'water chestnut' first.", "simulated_call"),
    ("validate_descriptors(['peanut jam'])", "simulated_call"),
    ("The get_parent lookup returned no parents for 'peanut jam'.", "reported_result"),
    ("The tool confirmed that rose is under floral.", "reported_result"),
    ("get_parent('milk') → result: 'dairy'", "reported_result"),
])
def test_flagged(text, kind):
    kinds, _ = flags.classify(rec(text))
    assert kind in kinds and kinds & set(flags.FLAG_KINDS)


@pytest.mark.parametrize("text", [
    "The instructions say to only treat confirmed get_parent results as positive evidence, so I answer from knowledge. Therefore, I select (B)",
    "I don't have access to any tools here, so I will reason directly. Therefore, I select (A)",
    "Peanut jam is nutty. Therefore, I select (A, B)",
    "I'll use my knowledge of the flavor wheel graph. Therefore, I select (A)",
    "Let me check whether rose appears in the graph of SCAA nodes. Therefore, I select (B)",
    "I need to check the graph: floral is a top-level category. Therefore, I select (A)",
])
def test_not_flagged(text):
    kinds, _ = flags.classify(rec(text))
    assert not kinds & set(flags.FLAG_KINDS)


def test_hedged_tool_reasoning_is_not_an_invented_result():
    kinds, _ = flags.classify(rec("If so, get_parent('borscht') would return its parent. Therefore, I select (A)"))
    assert "hypothetical_tool" in kinds and "reported_result" not in kinds
    kinds, _ = flags.classify(rec("get_parent('blue cheese') returns ['sour/fermented']. Therefore, I select (B)"))
    assert "reported_result" in kinds


def test_parse_error_flagged_but_f_none_answer_not():
    assert "no_final_answer" in flags.classify(rec("…", status="parse_error", answer=None))[0]
    assert "no_final_answer" not in flags.classify(rec("long essay", answer=None))[0]


def test_reasoning_text_is_checked():
    kinds, where = flags.classify(rec("Therefore, I select (A)", thinking="Let me call get_parent on rose."))
    assert "simulated_call" in kinds and where["simulated_call"].startswith("thinking")
