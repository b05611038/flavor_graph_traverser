#!/usr/bin/env python3
"""
Pre-flight Check

Validates that everything is ready before running a real experiment.
Run this before any OpenRouter benchmark to catch setup issues early.

Usage:
    python scripts/experiment/preflight_check.py
    python scripts/experiment/preflight_check.py --models anthropic/claude-sonnet-4.6 openai/gpt-5.4
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Auto-load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PASS = "✓"
FAIL = "✗"
WARN = "⚠"


def check_api_key():
    """Check that OpenRouter API key is available."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if key and key.startswith("sk-or-"):
        print(f"  {PASS} OPENROUTER_API_KEY set ({key[:12]}...)")
        return True
    elif key:
        print(f"  {WARN} OPENROUTER_API_KEY set but doesn't start with 'sk-or-' — may be invalid")
        return True
    else:
        print(f"  {FAIL} OPENROUTER_API_KEY not set")
        print(f"    Fix: export OPENROUTER_API_KEY=sk-or-v1-... or add to .env file")
        return False


def check_graph():
    """Check that the tool graph loads correctly."""
    graph_path = Path("data/graphs/coffee_flavor_wheel.pkl")
    if not graph_path.exists():
        print(f"  {FAIL} Graph file not found: {graph_path}")
        return False

    try:
        from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
        data = load_graph_data(str(graph_path))
        graph = CoffeeDescriptionGraph(
            data['descriptions'], data['connections'], root=data['root']
        )
        n_nodes = len(graph.descriptions)
        print(f"  {PASS} Graph loaded: {n_nodes} nodes")
        return True
    except Exception as e:
        print(f"  {FAIL} Graph load error: {e}")
        return False


def check_questions():
    """Check that benchmark questions exist and are well-formed."""
    q_path = Path("data/questions/benchmark_questions.json")
    if not q_path.exists():
        print(f"  {FAIL} Questions file not found: {q_path}")
        return False

    try:
        with open(q_path) as f:
            data = json.load(f)

        if isinstance(data, dict) and "questions" in data:
            questions = data["questions"]
        else:
            questions = data

        n_total = len(questions)
        active = [q for q in questions if q.get("status") != "rejected"]
        n_active = len(active)

        # Count by task type
        from collections import Counter
        types = Counter()
        for q in active:
            tt = q.get("task_type", q.get("id", "?").split("_")[0])
            types[tt.split("_")[0].upper()] += 1

        print(f"  {PASS} Questions loaded: {n_active} active ({n_total} total)")
        print(f"    Task types: {dict(sorted(types.items()))}")

        # Validate required fields
        required = {"id", "text", "correct_answer"}
        missing = []
        for q in active[:5]:
            for field in required:
                if field not in q:
                    missing.append(f"{q.get('id', '?')}: missing '{field}'")
        if missing:
            print(f"  {WARN} Sample validation issues: {missing[:3]}")
            return False

        return True
    except Exception as e:
        print(f"  {FAIL} Questions parse error: {e}")
        return False


def check_configs():
    """Check that experiment configs are consistent."""
    ok = True

    # models.yaml
    models_path = Path("configs/models.yaml")
    if models_path.exists():
        import yaml
        with open(models_path) as f:
            cfg = yaml.safe_load(f)

        n_models = sum(
            len(cfg.get(s, []))
            for s in ("closed_source", "open_source")
        )
        enabled = sum(
            1 for s in ("closed_source", "open_source")
            for m in cfg.get(s, [])
            if m.get("enabled", True)
        )
        judges = [j for j in cfg.get("judges", []) if j.get("enabled", True)]
        print(f"  {PASS} models.yaml: {enabled}/{n_models} models enabled, {len(judges)} judge(s)")
    else:
        print(f"  {FAIL} models.yaml not found")
        ok = False

    # conditions.yaml
    cond_path = Path("configs/conditions.yaml")
    if cond_path.exists():
        import yaml
        with open(cond_path) as f:
            cond_cfg = yaml.safe_load(f)
        conditions = list(cond_cfg.get("conditions", {}).keys())
        print(f"  {PASS} conditions.yaml: {conditions}")
    else:
        print(f"  {FAIL} conditions.yaml not found")
        ok = False

    # experiment.yaml points to correct questions
    exp_path = Path("configs/experiment.yaml")
    if exp_path.exists():
        import yaml
        with open(exp_path) as f:
            exp_cfg = yaml.safe_load(f)
        q_file = exp_cfg.get("data", {}).get("questions_file", "")
        if "benchmark_questions" in q_file:
            print(f"  {PASS} experiment.yaml → {q_file}")
        else:
            print(f"  {WARN} experiment.yaml → {q_file} (expected benchmark_questions.json)")
            ok = False

    return ok


def check_dependencies():
    """Check required Python packages."""
    ok = True
    for pkg, import_name in [
        ("python-igraph", "igraph"),
        ("pyyaml", "yaml"),
        ("requests", "requests"),
        ("python-dotenv", "dotenv"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            print(f"  {FAIL} Missing package: {pkg}")
            ok = False

    if ok:
        print(f"  {PASS} All required packages installed")
    return ok


def check_api_connectivity(models=None):
    """Optional: test actual API connectivity with a minimal request."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print(f"  {WARN} Skipping API connectivity (no API key)")
        return True

    import requests as req
    try:
        resp = req.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        resp.raise_for_status()
        available = {m["id"] for m in resp.json().get("data", [])}
        print(f"  {PASS} OpenRouter API reachable ({len(available)} models available)")

        if models:
            for m in models:
                if m in available:
                    print(f"    {PASS} {m}")
                else:
                    print(f"    {FAIL} {m} — NOT available on OpenRouter")
        return True
    except Exception as e:
        print(f"  {FAIL} API connectivity failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Pre-flight check for experiments")
    parser.add_argument("--models", nargs="+", help="Specific model IDs to verify availability")
    parser.add_argument("--skip-api", action="store_true", help="Skip API connectivity check")
    args = parser.parse_args()

    print("=" * 60)
    print("Pre-flight Check")
    print("=" * 60)
    print()

    all_ok = True

    print("[1/5] Dependencies")
    all_ok &= check_dependencies()
    print()

    print("[2/5] API Key")
    all_ok &= check_api_key()
    print()

    print("[3/5] Data Files")
    all_ok &= check_graph()
    all_ok &= check_questions()
    print()

    print("[4/5] Configs")
    all_ok &= check_configs()
    print()

    print("[5/5] API Connectivity")
    if args.skip_api:
        print(f"  {WARN} Skipped (--skip-api)")
    else:
        all_ok &= check_api_connectivity(args.models)
    print()

    print("=" * 60)
    if all_ok:
        print(f"{PASS} ALL CHECKS PASSED — ready to run experiment")
    else:
        print(f"{FAIL} SOME CHECKS FAILED — fix issues above before running")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
