"""
Tests for the follow-up conditions in configs/conditions.yaml and their wiring
(prompt_only, tool_resolved, graph_in_context) plus the selective re-run filter.
"""

import json
from unittest.mock import Mock

import pytest

from FlavorGraphTraverser.evaluation import QuestionEvaluator
from FlavorGraphTraverser.evaluation.client.base import BaseClient, LLMResponse, UsageStats
from FlavorGraphTraverser.evaluation.tools import build_executor
from FlavorGraphTraverser.evaluation.utils import load_conditions_config


@pytest.fixture(scope="module")
def cfg():
    return load_conditions_config()


@pytest.fixture
def client():
    c = Mock(spec=BaseClient)
    c.model = "test-model"
    c.query.return_value = LLMResponse(
        content="Therefore, I select (C)",
        usage=UsageStats(input_tokens=1, output_tokens=1, total_tokens=2),
    )
    return c


QUESTION = {
    "id": "TEST_001",
    "text": "Which root category does 'chocolate' belong to?",
    "options": {"A": "fruity", "B": "floral", "C": "nutty/cocoa", "D": "spices"},
    "correct_answer": "C",
}


class TestConditionsConfig:
    def test_original_conditions_untouched(self, cfg):
        c = cfg["conditions"]
        assert c["no_tool"]["system_prompt"] == ""
        assert c["no_tool"]["tools_enabled"] is False
        assert c["tool"]["tools_enabled"] is True
        assert c["tool"]["max_reasoning_calls"] == 5
        assert c["tool"].get("label_resolution", "exact") == "exact"
        assert "Only treat confirmed get_parent results as positive evidence" in c["tool"]["system_prompt"]

    def test_tool_resolved_differs_from_tool_only_in_label_resolution(self, cfg):
        tool, res = cfg["conditions"]["tool"], cfg["conditions"]["tool_resolved"]
        keys = {"tools_enabled", "max_reasoning_calls", "max_validate_repeats", "system_prompt"}
        assert {k: tool[k] for k in keys} == {k: res[k] for k in keys}
        assert res["label_resolution"] == "resolve"
        assert not res.get("draft")

    def test_prompt_only_uses_tool_prompt_without_tools(self, cfg):
        po = cfg["conditions"]["prompt_only"]
        assert po["tools_enabled"] is False
        assert po["system_prompt"] == cfg["conditions"]["tool"]["system_prompt"]

    def test_prompt_only_noaccess_drops_only_first_sentence(self, cfg):
        tool = cfg["conditions"]["tool"]["system_prompt"]
        first, rest = tool.split("\n", 1)
        assert first == "You have access to a coffee flavor graph database via the provided tools."
        alt = cfg["conditions"]["prompt_only_noaccess"]
        assert alt["system_prompt"] == rest
        assert alt["tools_enabled"] is False and not alt.get("draft")

    def test_draft_conditions_flagged(self, cfg):
        # verbatim prompt_only stays a pilot-only draft; the run conditions are final
        assert cfg["conditions"]["prompt_only"].get("draft") is True
        assert not cfg["conditions"]["prompt_only_noaccess"].get("draft")
        assert not cfg["conditions"]["graph_in_context"].get("draft")

    def test_prompt_only_sends_tool_prompt_and_no_tools(self, cfg, client, coffee_flavor_wheel_graph):
        ex = build_executor(coffee_flavor_wheel_graph, cfg["conditions"]["prompt_only"])
        ev = QuestionEvaluator(client, ex, "prompt_only", config=cfg)
        result = ev.evaluate(QUESTION)
        assert result.status == "success"
        messages = client.query.call_args.args[0]
        assert messages[0].content == cfg["conditions"]["tool"]["system_prompt"].rstrip()
        assert client.query.call_args.kwargs.get("tools") is None

    def test_graph_in_context_inlines_graph(self, cfg, client, coffee_flavor_wheel_graph):
        ex = build_executor(coffee_flavor_wheel_graph, cfg["conditions"]["graph_in_context"])
        ev = QuestionEvaluator(client, ex, "graph_in_context", config=cfg)
        assert "{tool_graph}" not in ev.system_prompt
        assert '"floral (inner layer)": {' in ev.system_prompt
        assert '"jasmine": {}' in ev.system_prompt
        assert ev.run_meta["graph_render_format"] == "json"
        assert ev.run_meta["graph_aliases"] == "resolver"
        assert "{name_aliases}" not in ev.system_prompt
        assert '"green/vegetable": "green/vegetative (inner layer)"' in ev.system_prompt
        ev.evaluate(QUESTION)
        assert client.query.call_args.kwargs.get("tools") is None

    def test_alias_placeholder_required(self, cfg, client, coffee_flavor_wheel_graph):
        bad = json.loads(json.dumps(cfg))
        c = bad["conditions"]["graph_in_context"]
        c["system_prompt"] = c["system_prompt"].replace("{name_aliases}", "")
        ex = build_executor(coffee_flavor_wheel_graph, {})
        with pytest.raises(ValueError, match="name_aliases"):
            QuestionEvaluator(client, ex, "graph_in_context", config=bad)

    def test_unfilled_alias_placeholder_rejected(self, cfg, client, coffee_flavor_wheel_graph):
        bad = json.loads(json.dumps(cfg))
        bad["conditions"]["graph_in_context"]["graph_aliases"] = "none"
        ex = build_executor(coffee_flavor_wheel_graph, {})
        with pytest.raises(ValueError, match="unfilled"):
            QuestionEvaluator(client, ex, "graph_in_context", config=bad)

    def test_graph_in_context_requires_placeholder(self, cfg, client, coffee_flavor_wheel_graph):
        bad = json.loads(json.dumps(cfg))
        bad["conditions"]["graph_in_context"]["system_prompt"] = "no placeholder"
        ex = build_executor(coffee_flavor_wheel_graph, {})
        with pytest.raises(ValueError, match="placeholder"):
            QuestionEvaluator(client, ex, "graph_in_context", config=bad)

    def test_tool_resolved_executor_resolves(self, cfg, coffee_flavor_wheel_graph):
        ex = build_executor(coffee_flavor_wheel_graph, cfg["conditions"]["tool_resolved"])
        assert ex.validate_descriptors(["floral"])["valid"] == ["floral"]
        ex_tool = build_executor(coffee_flavor_wheel_graph, cfg["conditions"]["tool"])
        assert ex_tool.validate_descriptors(["floral"])["invalid"] == ["floral"]


class TestSelectiveRerun:
    def test_only_pairs_filters_questions(self, tmp_path, coffee_flavor_wheel_path, monkeypatch):
        from FlavorGraphTraverser.evaluation import batch_runner as br

        questions = [dict(QUESTION, id=f"Q{i}") for i in range(4)]
        qfile = tmp_path / "q.json"
        qfile.write_text(json.dumps({"questions": questions}))

        seen = []

        class FakeEvaluator:
            def __init__(self, client, executor, condition, **kw):
                self.condition = condition
                self.run_meta = {"condition_fingerprint": "fake"}

            def evaluate(self, q):
                seen.append((self.condition, q["id"]))
                raise RuntimeError("stop")  # runner logs and continues; nothing to serialize

        monkeypatch.setattr(br, "QuestionEvaluator", FakeEvaluator)
        monkeypatch.setattr(br, "create_client", lambda **kw: Mock())
        monkeypatch.setattr(br.BatchRunner, "_save_results", lambda *a, **k: None)

        runner = br.BatchRunner(str(qfile), coffee_flavor_wheel_path, output_dir=str(tmp_path / "out"),
                                enable_cache=False, verbose=False)
        runner.run(models=["m"], conditions=["tool", "tool_resolved"],
                   only_pairs={("m", "tool_resolved"): {"Q1", "Q3"}})
        assert seen == [("tool_resolved", "Q1"), ("tool_resolved", "Q3")]


class TestToolRerun:
    def test_tool_rerun_identical_to_tool(self, cfg):
        from FlavorGraphTraverser.evaluation.utils import condition_fingerprint
        c = cfg["conditions"]
        assert condition_fingerprint(c["tool_rerun"], cfg["common"]) == condition_fingerprint(c["tool"], cfg["common"])
        assert condition_fingerprint(c["tool_resolved"], cfg["common"]) != condition_fingerprint(c["tool"], cfg["common"])

    def test_fingerprint_changes_with_prompt_and_draft(self, cfg):
        from FlavorGraphTraverser.evaluation.utils import condition_fingerprint
        po = dict(cfg["conditions"]["prompt_only"])
        fp = condition_fingerprint(po, cfg["common"])
        assert condition_fingerprint(dict(po, system_prompt="other"), cfg["common"]) != fp
        assert condition_fingerprint(dict(po, draft=False), cfg["common"]) != fp
        assert condition_fingerprint(dict(po, name="renamed"), cfg["common"]) == fp


class TestRunMeta:
    def test_results_are_stamped(self, cfg, client, coffee_flavor_wheel_graph):
        ex = build_executor(coffee_flavor_wheel_graph, cfg["conditions"]["graph_in_context"])
        result = QuestionEvaluator(client, ex, "graph_in_context", config=cfg).evaluate(QUESTION)
        assert result.run_meta["draft"] is False
        assert result.run_meta["graph_names"] == "corrected"
        ex2 = build_executor(coffee_flavor_wheel_graph, cfg["conditions"]["prompt_only"])
        assert QuestionEvaluator(client, ex2, "prompt_only", config=cfg).evaluate(QUESTION).run_meta["draft"] is True
        assert len(result.run_meta["condition_fingerprint"]) == 12

    def test_graph_in_context_corrected_names(self, cfg, client, coffee_flavor_wheel_graph):
        ex = build_executor(coffee_flavor_wheel_graph, {})
        ev = QuestionEvaluator(client, ex, "graph_in_context", config=cfg)
        assert "grapefruit" in ev.system_prompt and "graphfruit" not in ev.system_prompt


def _runner(tmp_path, coffee_flavor_wheel_path, monkeypatch, merged_path=None, n=2):
    from FlavorGraphTraverser.evaluation import batch_runner as br
    qfile = tmp_path / "q.json"
    qfile.write_text(json.dumps({"questions": [dict(QUESTION, id=f"Q{i}") for i in range(n)]}))
    monkeypatch.setattr(br, "create_client", lambda **kw: Mock(model="m"))
    return br, br.BatchRunner(str(qfile), coffee_flavor_wheel_path, output_dir=str(tmp_path / "root" / "run"),
                              enable_cache=True, verbose=False, merged_path=merged_path)


class TestBatchRunnerGuards:
    def test_draft_refused_without_allow(self, tmp_path, coffee_flavor_wheel_path, monkeypatch):
        br, runner = _runner(tmp_path, coffee_flavor_wheel_path, monkeypatch)
        with pytest.raises(ValueError, match="draft"):
            runner.run(models=["m"], conditions=["prompt_only"])

    def test_stale_cache_not_reused(self, tmp_path, coffee_flavor_wheel_path, monkeypatch):
        br, runner = _runner(tmp_path, coffee_flavor_wheel_path, monkeypatch, n=1)
        runner.results_cache["m/tool/Q0"] = {"run_meta": {"condition_fingerprint": "old"}}
        assert runner._is_cached("m", "tool", "Q0", "new") is False
        assert runner._is_cached("m", "tool", "Q0", "old") is True
        runner.results_cache["m/tool/Q0"] = {"question_id": "Q0"}  # legacy record without run_meta
        assert runner._is_cached("m", "tool", "Q0", "new") is True

    def test_merge_stays_inside_its_root(self, tmp_path, coffee_flavor_wheel_path, monkeypatch):
        from FlavorGraphTraverser.evaluation.batch_runner import merge_results_tree
        (tmp_path / "a" / "run1").mkdir(parents=True)
        (tmp_path / "b" / "run2").mkdir(parents=True)
        rec = lambda c: {"question_id": "Q", "model": "m", "condition": c}
        (tmp_path / "a" / "run1" / "results.json").write_text(json.dumps({"results": [rec("tool")]}))
        (tmp_path / "b" / "run2" / "results.json").write_text(json.dumps({"results": [rec("tool_rerun")]}))
        merge_results_tree(str(tmp_path / "b" / "merged_results.json"))
        merged = json.loads((tmp_path / "b" / "merged_results.json").read_text())["results"]
        assert [r["condition"] for r in merged] == ["tool_rerun"]
        assert not (tmp_path / "a" / "merged_results.json").exists()


class TestRunExperimentCli:
    """CLI guards trip before any API access (no key needed)."""

    def _run(self, *args):
        import subprocess, sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        return subprocess.run([sys.executable, "scripts/experiment/run_experiment.py", "--models", "x/y", *args],
                              cwd=root, capture_output=True, text=True, timeout=120)

    def test_draft_condition_refused(self):
        p = self._run("--conditions", "prompt_only", "--output", "results_revision/_test_never_created", "--no-merge")
        assert p.returncode == 1 and "draft" in p.stdout

    def test_revision_output_needs_explicit_merge_target(self):
        p = self._run("--conditions", "no_tool", "--output", "results_revision/_test_never_created")
        assert p.returncode == 1 and "--no-merge" in p.stdout

    def test_revision_condition_cannot_merge_into_original(self):
        p = self._run("--conditions", "tool_resolved", "--output", "results/_test_never_created")
        assert p.returncode == 1 and "results_revision" in p.stdout


class TestFingerprintContent:
    """Fingerprints must cover what the model sees, but leave the original conditions unchanged."""

    def _fp(self, cfg, client, graph, condition):
        ex = build_executor(graph, cfg["conditions"][condition])
        return QuestionEvaluator(client, ex, condition, config=cfg).run_meta["condition_fingerprint"]

    def test_original_conditions_pinned(self, cfg, client, coffee_flavor_wheel_graph):
        # Fingerprints of the April 2026 conditions; a change here would make every
        # follow-up re-run of `tool` look like a different condition.
        assert self._fp(cfg, client, coffee_flavor_wheel_graph, "tool") == "f36063f69620"
        assert self._fp(cfg, client, coffee_flavor_wheel_graph, "tool_rerun") == "f36063f69620"

    def test_alias_table_change_changes_fingerprints(self, cfg, client, coffee_flavor_wheel_graph, monkeypatch):
        from FlavorGraphTraverser.evaluation.tools import label_resolver as lr
        before = {c: self._fp(cfg, client, coffee_flavor_wheel_graph, c)
                  for c in ("tool_resolved", "graph_in_context", "tool")}
        monkeypatch.setitem(lr.DEFAULT_EXTRA_ALIASES, "test alias", "rose")
        after = {c: self._fp(cfg, client, coffee_flavor_wheel_graph, c)
                 for c in ("tool_resolved", "graph_in_context", "tool")}
        assert after["tool_resolved"] != before["tool_resolved"]
        assert after["tool"] == before["tool"]

    def test_rendered_graph_change_changes_fingerprint(self, cfg, client, coffee_flavor_wheel_graph, monkeypatch):
        from FlavorGraphTraverser.evaluation import evaluator as evmod
        before = self._fp(cfg, client, coffee_flavor_wheel_graph, "graph_in_context")
        monkeypatch.setattr(evmod, "render_graph", lambda g, fmt, name_map=None: "{}")
        assert self._fp(cfg, client, coffee_flavor_wheel_graph, "graph_in_context") != before

    def test_run_meta_label_resolution_from_executor(self, cfg, client, coffee_flavor_wheel_graph):
        ex = build_executor(coffee_flavor_wheel_graph, {"label_resolution": "resolve"})
        meta = QuestionEvaluator(client, ex, "tool", config=cfg).run_meta
        assert meta["label_resolution"] == "resolve"

    def test_graph_aliases_without_graph_in_context_rejected(self, cfg, client, coffee_flavor_wheel_graph):
        bad = json.loads(json.dumps(cfg))
        bad["conditions"]["prompt_only"]["graph_aliases"] = "resolver"
        with pytest.raises(ValueError, match="graph_aliases"):
            QuestionEvaluator(client, build_executor(coffee_flavor_wheel_graph, {}), "prompt_only", config=bad)

    def test_missing_render_format_rejected(self, cfg, client, coffee_flavor_wheel_graph):
        bad = json.loads(json.dumps(cfg))
        del bad["conditions"]["graph_in_context"]["graph_render_format"]
        with pytest.raises(ValueError, match="graph_render_format"):
            QuestionEvaluator(client, build_executor(coffee_flavor_wheel_graph, {}), "graph_in_context", config=bad)


class TestNoToolPathsIcl:
    @pytest.mark.parametrize("condition", ["prompt_only", "prompt_only_noaccess", "graph_in_context"])
    def test_icl_mode_sends_no_tool_protocol(self, cfg, client, coffee_flavor_wheel_graph, condition):
        ex = build_executor(coffee_flavor_wheel_graph, cfg["conditions"][condition])
        ev = QuestionEvaluator(client, ex, condition, config=cfg, tool_mode="icl")
        ev.evaluate(QUESTION)
        assert client.query.call_count == 1
        sent = client.query.call_args.args[0]
        assert client.query.call_args.kwargs.get("tools") is None
        assert not any("TOOL_CALL" in m.content for m in sent)
        assert "limited budget" not in sent[0].content


class TestResolverFingerprintCoversAllRules:
    def test_plural_rule_change_changes_fingerprint(self, cfg, client, coffee_flavor_wheel_graph, monkeypatch):
        from FlavorGraphTraverser.evaluation.tools import label_resolver as lr
        def fp():
            ex = build_executor(coffee_flavor_wheel_graph, cfg["conditions"]["tool_resolved"])
            return QuestionEvaluator(client, ex, "tool_resolved", config=cfg).run_meta["condition_fingerprint"]
        before = fp()
        monkeypatch.setattr(lr, "_number_forms", lambda key: [])
        assert fp() != before

    def test_served_provenance_recorded(self, cfg, client, coffee_flavor_wheel_graph):
        client.query.return_value.resolved_model = "vendor/model-2026"
        client.query.return_value.provider = "SomeProvider"
        ex = build_executor(coffee_flavor_wheel_graph, cfg["conditions"]["no_tool"])
        res = QuestionEvaluator(client, ex, "no_tool", config=cfg).evaluate(QUESTION)
        assert res.run_meta["served"] == [{"model": "vendor/model-2026", "provider": "SomeProvider"}]


class TestCacheRetriesApiErrors:
    def test_api_error_not_reused(self, tmp_path, coffee_flavor_wheel_path, monkeypatch):
        br, runner = _runner(tmp_path, coffee_flavor_wheel_path, monkeypatch)
        runner.results_cache["m/no_tool/Q0"] = {"status": "api_error", "run_meta": None}
        runner.results_cache["m/no_tool/Q1"] = {"status": "success", "run_meta": None}
        assert runner._is_cached("m", "no_tool", "Q0") is False
        assert runner._is_cached("m", "no_tool", "Q1") is True

    def test_api_error_in_errors_not_reused(self, tmp_path, coffee_flavor_wheel_path, monkeypatch):
        """Results written before the status fix: api_error hidden under another status."""
        br, runner = _runner(tmp_path, coffee_flavor_wheel_path, monkeypatch)
        for i, st in enumerate(("parse_error", "success", "no_judge")):
            runner.results_cache[f"m/tool/Q{i}"] = {"status": st, "run_meta": None,
                                                     "errors": [{"type": "api_error", "message": "402"}]}
            assert runner._is_cached("m", "tool", f"Q{i}") is False
        runner.results_cache["m/tool/Q9"] = {"status": "success", "run_meta": None,
                                             "errors": [{"type": "tool_error", "message": "bad arg"}]}
        assert runner._is_cached("m", "tool", "Q9") is True
