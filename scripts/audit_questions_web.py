#!/usr/bin/env python3
"""
Question Auditor Web Interface

Simple web interface for reviewing questions one-by-one.
Features:
- Show question with LLM view and annotated view
- Confirm or Flag buttons
- Duplicate detection
- Progress tracking
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, request
import json
from FlavorGraphTraverser.evaluation.question_auditor import (
    QuestionAuditor,
    format_question_for_display
)

# Get project root for template directory
project_root = Path(__file__).parent.parent
template_dir = project_root / "templates"

app = Flask(__name__, template_folder=str(template_dir))

# Global state
auditor = None
all_questions = []
current_index = 0
skipped_questions = set()  # Track skipped questions in current session


def load_questions(questions_file: str):
    """Load questions from JSON file."""
    global all_questions
    with open(questions_file, 'r') as f:
        data = json.load(f)
        # Handle both list and dict formats
        if isinstance(data, list):
            all_questions = data
        elif isinstance(data, dict) and "questions" in data:
            all_questions = data["questions"]
        else:
            all_questions = []
    return all_questions


@app.route('/')
def index():
    """Main auditor page."""
    return render_template('auditor.html')


@app.route('/api/stats')
def get_stats():
    """Get audit statistics."""
    stats = auditor.get_stats()
    stats['total_questions'] = len(all_questions)
    stats['pending'] = stats['total_questions'] - stats['total_reviewed']
    stats['progress_percent'] = int((stats['confirmed'] / stats['total_questions']) * 100) if stats['total_questions'] > 0 else 0
    return jsonify(stats)


@app.route('/api/current')
def get_current_question():
    """Get current question to review."""
    global current_index, skipped_questions

    # Get pending questions
    all_ids = [q.get("id") for q in all_questions]
    pending_ids = auditor.get_pending_questions(all_ids)

    if not pending_ids:
        return jsonify({"done": True, "message": "All questions reviewed!"})

    # Get first pending question that hasn't been skipped
    current_question = None
    for q in all_questions:
        q_id = q.get("id")
        if q_id in pending_ids and q_id not in skipped_questions:
            current_question = q
            break

    if not current_question:
        # All pending questions have been skipped
        if skipped_questions:
            return jsonify({"done": True, "message": "All pending questions have been skipped!"})
        return jsonify({"done": True, "message": "All questions reviewed!"})

    # Check for duplicates
    confirmed_ids = auditor.get_confirmed_questions()
    confirmed_questions = [q for q in all_questions if q.get("id") in confirmed_ids]
    duplicate_id = auditor.check_duplicate(current_question, confirmed_questions)

    # Format for display
    formatted = format_question_for_display(current_question)
    formatted['is_duplicate'] = duplicate_id is not None
    formatted['duplicate_of'] = duplicate_id
    formatted['pending_count'] = len(pending_ids)

    return jsonify(formatted)


@app.route('/api/confirm', methods=['POST'])
def confirm_question():
    """Confirm current question."""
    data = request.get_json()
    question_id = data.get('question_id')
    notes = data.get('notes', '')

    auditor.confirm_question(question_id, notes)

    return jsonify({"success": True})


@app.route('/api/flag', methods=['POST'])
def flag_question():
    """Flag current question for review."""
    data = request.get_json()
    question_id = data.get('question_id')
    reason = data.get('reason', 'No reason provided')
    notes = data.get('notes', '')

    auditor.flag_question(question_id, reason, notes)

    # Save flag log for CLI review
    log_file = Path("data/flagged_questions.jsonl")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Find the question
    question = next((q for q in all_questions if q.get("id") == question_id), None)

    if question:
        log_entry = {
            "question_id": question_id,
            "question": question,
            "reason": reason,
            "notes": notes,
            "timestamp": auditor.states[question_id].timestamp
        }

        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    return jsonify({"success": True})


@app.route('/api/skip', methods=['POST'])
def skip_question():
    """Skip to next question without action."""
    global skipped_questions

    data = request.get_json()
    question_id = data.get('question_id')

    if question_id:
        skipped_questions.add(question_id)

    return jsonify({"success": True})


def main():
    """Run the web auditor."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Question Auditor Web Interface (Read/Write)",
        epilog="Note: This interface writes to the audit state file. "
               "Use review_audited_questions.py for read-only viewing."
    )
    parser.add_argument(
        'questions_file',
        help="Path to questions JSON file"
    )
    parser.add_argument(
        '--state-file',
        default=None,
        help="Path to audit state file (default: canonical location at data/audit_results/audit_state.json)"
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help="Port to run web server (default: 5000)"
    )

    args = parser.parse_args()

    # Initialize
    global auditor
    auditor = QuestionAuditor(state_file=args.state_file, read_only=False)

    # Load questions
    print(f"Loading questions from: {args.questions_file}")
    questions = load_questions(args.questions_file)
    print(f"Loaded {len(questions)} questions")

    # Show stats
    stats = auditor.get_stats()
    print(f"\nAudit Status:")
    print(f"  Confirmed: {stats['confirmed']}")
    print(f"  Flagged: {stats['flagged']}")
    print(f"  Pending: {len(questions) - stats['total_reviewed']}")

    # Create templates directory if needed
    templates_dir = Path(__file__).parent.parent / "templates"
    templates_dir.mkdir(exist_ok=True)

    print(f"\n{'='*70}")
    print(f"🔍 Question Auditor Web Interface")
    print(f"{'='*70}")
    print(f"\nOpen in browser: http://localhost:{args.port}")
    print(f"\nPress Ctrl+C to stop")
    print(f"{'='*70}\n")

    # Run server
    app.run(debug=True, port=args.port, use_reloader=False)


if __name__ == '__main__':
    main()
