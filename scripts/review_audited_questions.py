#!/usr/bin/env python3
"""
Web interface to review audited questions (confirmed and flagged).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import argparse
from flask import Flask, render_template, jsonify, request
from FlavorGraphTraverser.evaluation.question_auditor import QuestionAuditor, format_question_for_display

# Setup Flask with correct template directory
project_root = Path(__file__).parent.parent
template_dir = project_root / "templates"
app = Flask(__name__, template_folder=str(template_dir))

# Global state
questions_data = None
auditor = None
questions_file = None


def load_data(questions_path, audit_state_path, read_only=True):
    """Load questions and audit state."""
    global questions_data, auditor, questions_file

    questions_file = questions_path

    with open(questions_path, 'r') as f:
        questions_data = json.load(f)

    auditor = QuestionAuditor(state_file=audit_state_path, read_only=read_only)


@app.route('/')
def index():
    """Serve the review interface."""
    return render_template('review.html')


@app.route('/api/stats')
def get_stats():
    """Get audit statistics (with auto-reload)."""
    # Reload state from file to get latest changes
    auditor.reload_state()

    stats = auditor.get_stats()

    all_questions = questions_data['questions']
    total = len(all_questions)
    pending = total - stats['total_reviewed']

    return jsonify({
        'confirmed': stats['confirmed'],
        'flagged': stats['flagged'],
        'total_reviewed': stats['total_reviewed'],
        'pending': pending,
        'total': total
    })


@app.route('/api/confirmed')
def get_confirmed():
    """Get all confirmed questions (with auto-reload and task type filter)."""
    # Reload state from file to get latest changes
    auditor.reload_state()

    # Get task type filter from query parameter
    task_type_filter = request.args.get('task_type', None)

    confirmed_ids = auditor.get_confirmed_questions()

    questions = []
    for qid in confirmed_ids:
        q = next((q for q in questions_data['questions'] if q['id'] == qid), None)
        if q:
            # Apply task type filter if specified
            if task_type_filter and not q['task_type'].startswith(task_type_filter):
                continue

            display_q = format_question_for_display(q)
            display_q['id'] = q['id']
            display_q['task_type'] = q['task_type']
            display_q['descriptor'] = q.get('_objects', {}).get('descriptor', 'N/A')
            questions.append(display_q)

    return jsonify({'questions': questions})


@app.route('/api/flagged')
def get_flagged():
    """Get all flagged questions (with auto-reload and task type filter)."""
    # Reload state from file to get latest changes
    auditor.reload_state()

    # Get task type filter from query parameter
    task_type_filter = request.args.get('task_type', None)

    flagged_ids = auditor.get_flagged_questions()

    questions = []
    for qid in flagged_ids:
        q = next((q for q in questions_data['questions'] if q['id'] == qid), None)
        if q:
            # Apply task type filter if specified
            if task_type_filter and not q['task_type'].startswith(task_type_filter):
                continue

            display_q = format_question_for_display(q)
            display_q['id'] = q['id']
            display_q['task_type'] = q['task_type']
            display_q['descriptor'] = q.get('_objects', {}).get('descriptor', 'N/A')

            # Get flag reason
            state = auditor.states.get(qid)
            if state:
                display_q['flag_reason'] = state.flag_reason
                display_q['notes'] = state.notes

            questions.append(display_q)

    return jsonify({'questions': questions})


@app.route('/api/unconfirm', methods=['POST'])
def unconfirm():
    """Move question from confirmed back to pending."""
    data = request.json
    question_id = data.get('question_id')

    if question_id in auditor.states:
        auditor.unflag_question(question_id)  # This removes from states (back to pending)

    return jsonify({'status': 'success'})


@app.route('/api/unflag', methods=['POST'])
def unflag():
    """Move question from flagged back to pending."""
    data = request.json
    question_id = data.get('question_id')

    if question_id in auditor.states:
        auditor.unflag_question(question_id)

    return jsonify({'status': 'success'})


@app.route('/api/confirm_flagged', methods=['POST'])
def confirm_flagged():
    """Move question from flagged to confirmed."""
    data = request.json
    question_id = data.get('question_id')

    auditor.confirm_question(question_id)

    return jsonify({'status': 'success'})


def main():
    parser = argparse.ArgumentParser(
        description='Review audited questions (Read-Only Interface)',
        epilog='This is a READ-ONLY interface that auto-reloads state changes. '
               'Use audit_questions_web.py to modify question status.'
    )
    parser.add_argument('questions_file', help='Path to questions JSON file')
    parser.add_argument(
        '--audit-state',
        default=None,
        help='Path to audit state file (default: canonical location at data/audit_results/audit_state.json)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5001,
        help='Port to run on (default: 5001)'
    )
    parser.add_argument(
        '--read-write',
        action='store_true',
        help='Enable write access (NOT recommended - use audit_questions_web.py instead)'
    )

    args = parser.parse_args()

    # Determine read-only mode
    read_only = not args.read_write

    # Load data
    print(f"Loading questions from: {args.questions_file}")
    print(f"Loading audit state from: {args.audit_state or 'canonical location'}")
    print(f"Mode: {'READ-WRITE (not recommended)' if not read_only else 'READ-ONLY (auto-reload enabled)'}")
    load_data(args.questions_file, args.audit_state, read_only=read_only)

    stats = auditor.get_stats()
    print(f"\nAudit Status:")
    print(f"  Confirmed: {stats['confirmed']}")
    print(f"  Flagged: {stats['flagged']}")
    print(f"  State file: {auditor.state_file}")
    print()

    print("="*70)
    print(f"📋 Question Review Interface ({'READ-ONLY' if read_only else 'READ-WRITE'})")
    print("="*70)
    print()
    print(f"Open in browser: http://localhost:{args.port}")
    if read_only:
        print(f"Auto-reload: Updates from auditor will appear automatically")
    print()
    print("Press Ctrl+C to stop")
    print("="*70)
    print()

    app.run(host='127.0.0.1', port=args.port, debug=True)


if __name__ == '__main__':
    main()
