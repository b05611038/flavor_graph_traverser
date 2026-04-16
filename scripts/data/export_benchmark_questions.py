#!/usr/bin/env python3
"""
Export Benchmark Questions

Regenerates data/questions/benchmark_questions.json from the current
audit state (confirmed questions only, rejected excluded).

Run this after confirming new questions in the auditing site.

Usage:
    python scripts/export_benchmark_questions.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

QUESTIONS_FILE = project_root / "data" / "questions" / "all_questions_system.json"
AUDIT_STATE_FILE = project_root / "data" / "audit_results" / "audit_state.json"
OUTPUT_FILE = project_root / "data" / "questions" / "benchmark_questions.json"


def main():
    with open(QUESTIONS_FILE) as f:
        data = json.load(f)
    with open(AUDIT_STATE_FILE) as f:
        audit = json.load(f)

    confirmed_ids = {qid for qid, v in audit.items() if v.get("status") == "confirmed"}
    confirmed_qs = [
        q for q in data["questions"]
        if q.get("id") in confirmed_ids and q.get("status") != "rejected"
    ]

    types = Counter(q.get("task_type", "MISSING") for q in confirmed_qs)

    output = {
        "metadata": {
            "description": "Benchmark question set — audited and confirmed questions only",
            "total_questions": len(confirmed_qs),
            "created": datetime.now().isoformat(),
            "source": "all_questions_system.json filtered by audit_state.json (status=confirmed)",
            "by_task_type": dict(sorted(types.items())),
        },
        "questions": confirmed_qs,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Exported {len(confirmed_qs)} confirmed questions → {OUTPUT_FILE}")
    for task_type, count in sorted(types.items()):
        print(f"  {count:4d}  {task_type}")


if __name__ == "__main__":
    main()
