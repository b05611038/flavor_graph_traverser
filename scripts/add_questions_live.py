#!/usr/bin/env python3
"""
Add questions to the running auditor without restarting.

Usage:
    python scripts/add_questions_live.py <questions_file.json>
    python scripts/add_questions_live.py --reload
"""

import sys
import json
import requests
from pathlib import Path

AUDITOR_URL = "http://localhost:5000"


def add_questions(questions_file: str):
    """Add questions from a file to the running auditor."""
    # Load questions
    with open(questions_file) as f:
        data = json.load(f)

    # Send to auditor
    response = requests.post(f"{AUDITOR_URL}/api/add_questions", json=data)

    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            print(f"✓ {result['message']}")
            print(f"  Added: {result['added']}")
            if result.get("skipped_duplicates", 0) > 0:
                print(f"  Skipped duplicates: {result['skipped_duplicates']}")
            print(f"  New total: {result['new_total']}")
        else:
            print(f"✗ Failed: {result.get('message', 'Unknown error')}")
    else:
        print(f"✗ HTTP Error {response.status_code}")
        try:
            error = response.json().get("error", "Unknown error")
            print(f"  {error}")
        except:
            print(f"  {response.text}")


def reload_questions():
    """Reload questions from file."""
    response = requests.post(f"{AUDITOR_URL}/api/reload")

    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            print(f"✓ {result['message']}")
            stats = result["stats"]
            print(f"  Total: {stats['total']}")
            print(f"  Confirmed: {stats['confirmed']}")
            print(f"  Flagged: {stats['flagged']}")
            print(f"  Pending: {stats['pending']}")
        else:
            print(f"✗ Failed: {result.get('error', 'Unknown error')}")
    else:
        print(f"✗ HTTP Error {response.status_code}")
        try:
            error = response.json().get("error", "Unknown error")
            print(f"  {error}")
        except:
            print(f"  {response.text}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Add questions:  python scripts/add_questions_live.py <questions_file.json>")
        print("  Reload:         python scripts/add_questions_live.py --reload")
        sys.exit(1)

    if sys.argv[1] == "--reload":
        print("Reloading questions from file...")
        reload_questions()
    else:
        questions_file = sys.argv[1]
        if not Path(questions_file).exists():
            print(f"✗ File not found: {questions_file}")
            sys.exit(1)

        print(f"Adding questions from: {questions_file}")
        add_questions(questions_file)


if __name__ == "__main__":
    main()
