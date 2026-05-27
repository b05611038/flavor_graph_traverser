#!/usr/bin/env python3
"""
Unified Question Auditor Web Interface

Combines auditing and review into a single interface with navigation.
Run on port 5000 with both /audit and /review routes.

Usage:
    python scripts/question_auditor_unified.py [questions_file]
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, render_template, jsonify, request
import json
from datetime import datetime
from FlavorGraphTraverser.evaluation.question_auditor import (
    QuestionAuditor,
    format_question_for_display
)

from FlavorGraphTraverser.backup import backup_before_write
from FlavorGraphTraverser.evaluation.utils.answer_parser import compute_question_score

# Get project root for template directory
template_dir = project_root / "templates"

app = Flask(__name__, template_folder=str(template_dir))

# Global state
auditor = None
all_questions = []
questions_file = None
skipped_questions = set()  # Track skipped questions in current session
question_history = []  # Track question navigation history for "Previous" button

# Results viewer state
results_data = None  # Loaded results.json content
results_file = None
results_file_mtime = None  # Last-seen mtime for auto-reload


def load_results(file_path: str, verbose: bool = True):
    """Load evaluation results from JSON file.

    Always recomputes the per-row continuous score from source-of-truth fields
    (is_correct, judge_score, model_answer, correct_answer, status) so that
    stale scores in older results files are corrected at load time.
    """
    global results_data, results_file, results_file_mtime
    results_file = file_path
    with open(file_path, 'r') as f:
        results_data = json.load(f)
    try:
        results_file_mtime = os.path.getmtime(file_path)
    except OSError:
        results_file_mtime = None

    # Recompute scores defensively
    n_fixed = 0
    for r in results_data.get('results', []):
        new_score = compute_question_score(
            model_answer=r.get('model_answer'),
            correct_answer=r.get('correct_answer'),
            is_correct=r.get('is_correct', False),
            judge_score=r.get('judge_score'),
            status=r.get('status', 'success'),
        )
        if r.get('score') != new_score:
            r['score'] = new_score
            n_fixed += 1
    if verbose and n_fixed:
        print(f"  (recomputed {n_fixed} stale scores at load time)")
    return results_data


def maybe_reload_results():
    """Reload results.json if its mtime has changed since last load.

    Called at the start of each /api/results* request so the dashboard
    automatically picks up new model results as they are written by an
    in-progress experiment, without requiring a server restart.
    """
    global results_file_mtime
    if results_file is None:
        return
    try:
        current_mtime = os.path.getmtime(results_file)
    except OSError:
        return
    if results_file_mtime is None or current_mtime > results_file_mtime:
        try:
            n_before = len(results_data.get('results', [])) if results_data else 0
            load_results(results_file, verbose=False)
            n_after = len(results_data.get('results', []))
            if n_after != n_before:
                print(f"  ↻ Reloaded results.json: {n_before} → {n_after} rows")
        except (OSError, json.JSONDecodeError) as e:
            # File may be in the middle of being rewritten — keep old data
            print(f"  ⚠ Reload skipped (file mid-write?): {e}")

# Path to the master questions file — single source of truth for valid question IDs
MASTER_QUESTIONS_FILE = project_root / "data" / "questions" / "all_questions_system.json"

def get_valid_question_ids():
    """Return the set of question IDs that have actual data in the master file."""
    try:
        with open(MASTER_QUESTIONS_FILE) as f:
            data = json.load(f)
        return {q['id'] for q in data.get('questions', [])}
    except Exception:
        return set()


def load_questions(file_path: str):
    """Load questions from JSON file."""
    global all_questions, questions_file
    questions_file = file_path
    with open(file_path, 'r') as f:
        data = json.load(f)
        if isinstance(data, list):
            all_questions = data
        elif isinstance(data, dict) and "questions" in data:
            all_questions = data["questions"]
        else:
            all_questions = []
    return all_questions


# ============================================================================
# Auditor Routes (for reviewing/auditing questions)
# ============================================================================

@app.route('/')
def index():
    """Main page - redirect to auditor."""
    return render_template('auditor_unified.html', mode='audit')


@app.route('/audit')
def audit_page():
    """Auditor page."""
    return render_template('auditor_unified.html', mode='audit')


@app.route('/api/stats')
def get_stats():
    """Get audit statistics."""
    # Get IDs from current questions file
    all_ids = [q.get("id") for q in all_questions]

    # Filter stats to only questions in current file
    confirmed_in_file = [qid for qid in all_ids if auditor.get_status(qid) == "confirmed"]
    flagged_in_file = [qid for qid in all_ids if auditor.get_status(qid) == "flagged"]
    pending_in_file = auditor.get_pending_questions(all_ids)

    # Get cumulative stats — only count IDs that exist in the master questions file
    valid_ids = get_valid_question_ids()
    cumulative_confirmed = sum(
        1 for qid, s in auditor.states.items()
        if s.status == 'confirmed' and qid in valid_ids
    )
    cumulative_flagged = sum(
        1 for qid, s in auditor.states.items()
        if s.status == 'flagged' and qid in valid_ids
    )
    cumulative_total = sum(1 for qid in auditor.states if qid in valid_ids)

    stats = {
        # Current file stats
        'confirmed': len(confirmed_in_file),
        'flagged': len(flagged_in_file),
        'pending': len(pending_in_file),
        'total_questions': len(all_questions),
        'total_reviewed': len(confirmed_in_file) + len(flagged_in_file),
        'progress_percent': int((len(confirmed_in_file) / len(all_questions)) * 100) if len(all_questions) > 0 else 0,

        # Cumulative stats (all question types)
        'cumulative_confirmed': cumulative_confirmed,
        'cumulative_flagged': cumulative_flagged,
        'cumulative_total': cumulative_total,
        'cumulative_reviewed': cumulative_confirmed + cumulative_flagged
    }
    return jsonify(stats)


@app.route('/api/current')
def get_current_question():
    """Get current question to review."""
    global skipped_questions, question_history

    # Get pending questions
    all_ids = [q.get("id") for q in all_questions]
    pending_ids = auditor.get_pending_questions(all_ids)

    if not pending_ids:
        return jsonify({"done": True, "message": "All questions reviewed! Only confirmed and flagged (rejected) remain."})

    # Get first pending question that hasn't been skipped in this session
    current_question = None
    for q in all_questions:
        q_id = q.get("id")
        if q_id in pending_ids and q_id not in skipped_questions:
            current_question = q
            break

    if not current_question:
        # All pending questions have been skipped in this session
        # Cycle back: clear skipped set and start over
        if skipped_questions:
            skipped_questions.clear()
            # Get first pending question again
            for q in all_questions:
                q_id = q.get("id")
                if q_id in pending_ids:
                    current_question = q
                    break

            if current_question:
                # Add cycling message
                formatted = format_question_for_display(current_question)
                formatted['is_duplicate'] = False
                formatted['duplicate_of'] = None
                formatted['pending_count'] = len(pending_ids)
                formatted['cycling_message'] = "♻️ Cycled back to start of pending questions"
                formatted['has_previous'] = len(question_history) > 0
                return jsonify(formatted)

        return jsonify({"done": True, "message": "All questions reviewed!"})

    # Add to history (only if it's a new question, not from back navigation)
    if not question_history or question_history[-1] != current_question.get("id"):
        question_history.append(current_question.get("id"))
        # Keep history limited to last 50 questions
        if len(question_history) > 50:
            question_history.pop(0)

    # Check for duplicates
    confirmed_ids = auditor.get_confirmed_questions()
    confirmed_questions = [q for q in all_questions if q.get("id") in confirmed_ids]
    duplicate_id = auditor.check_duplicate(current_question, confirmed_questions)

    # Format for display
    formatted = format_question_for_display(current_question)
    formatted['is_duplicate'] = duplicate_id is not None
    formatted['duplicate_of'] = duplicate_id
    formatted['pending_count'] = len(pending_ids)
    formatted['has_previous'] = len(question_history) > 1  # Can go back if history > 1

    return jsonify(formatted)


@app.route('/api/confirm', methods=['POST'])
def confirm_question():
    """Confirm current question and create incremental backup."""
    global question_history

    data = request.get_json()
    question_id = data.get('question_id')
    notes = data.get('notes', '')

    # Confirm the question
    auditor.confirm_question(question_id, notes)

    # Remove from history so Previous doesn't go back to confirmed questions
    if question_id in question_history:
        question_history.remove(question_id)

    # Create incremental backup automatically
    backup_info = None
    try:
        backup_path = create_incremental_backup()
        if backup_path:
            backup_version = int(backup_path.stem.split('_')[1])
            backup_info = {
                "created": True,
                "version": backup_version,
                "message": f"Created backup_{backup_version}.json"
            }
        else:
            backup_info = {
                "created": False,
                "message": "Backup already exists with same confirmed count"
            }
    except Exception as e:
        print(f"Warning: Failed to create backup: {e}")
        backup_info = {
            "created": False,
            "error": str(e)
        }

    return jsonify({
        "success": True,
        "backup": backup_info
    })


@app.route('/api/flag', methods=['POST'])
def flag_question():
    """Flag current question."""
    global question_history

    data = request.get_json()
    question_id = data.get('question_id')
    reason = data.get('reason', '')
    notes = data.get('notes', '')

    # Combine reason and notes
    combined_notes = f"Reason: {reason}"
    if notes:
        combined_notes += f"\nNotes: {notes}"

    auditor.flag_question(question_id, combined_notes)

    # Remove from history so Previous doesn't go back to flagged questions
    if question_id in question_history:
        question_history.remove(question_id)

    return jsonify({"success": True})


@app.route('/api/skip', methods=['POST'])
def skip_question():
    """Skip current question (don't show again in this session)."""
    data = request.get_json()
    question_id = data.get('question_id')

    skipped_questions.add(question_id)

    return jsonify({"success": True})


@app.route('/api/previous', methods=['POST'])
def previous_question():
    """Go back to previous question."""
    global question_history, skipped_questions

    if len(question_history) <= 1:
        return jsonify({"success": False, "message": "No previous question available"})

    # Remove current question from history
    question_history.pop()

    # Get previous question ID
    prev_question_id = question_history[-1]

    # Remove from skipped if it was skipped
    if prev_question_id in skipped_questions:
        skipped_questions.remove(prev_question_id)

    # Find the previous question
    prev_question = None
    for q in all_questions:
        if q.get("id") == prev_question_id:
            prev_question = q
            break

    if not prev_question:
        return jsonify({"success": False, "message": "Previous question not found"})

    # Format and return
    formatted = format_question_for_display(prev_question)
    formatted['has_previous'] = len(question_history) > 1
    formatted['is_duplicate'] = False
    formatted['duplicate_of'] = None

    # Get pending count
    all_ids = [q.get("id") for q in all_questions]
    pending_ids = auditor.get_pending_questions(all_ids)
    formatted['pending_count'] = len(pending_ids)

    return jsonify(formatted)


# ============================================================================
# Review Routes (read-only view of confirmed questions)
# ============================================================================

@app.route('/review')
def review_page():
    """Review page - shows confirmed questions."""
    return render_template('auditor_unified.html', mode='review')


@app.route('/api/confirmed')
def get_confirmed_questions():
    """Get all confirmed questions, optionally filtered by task_type."""
    task_type_filter = request.args.get('task_type', '')
    confirmed_ids = auditor.get_confirmed_questions()
    confirmed = [q for q in all_questions if q.get("id") in confirmed_ids]

    if task_type_filter:
        confirmed = [q for q in confirmed if q.get('task_type') == task_type_filter]

    formatted = [format_question_for_display(q) for q in confirmed]

    return jsonify({
        "questions": formatted,
        "count": len(formatted)
    })


@app.route('/api/filter')
def filter_questions():
    """Filter questions by task type."""
    task_type = request.args.get('task_type', '')
    search = request.args.get('search', '').lower()

    confirmed_ids = auditor.get_confirmed_questions()
    confirmed = [q for q in all_questions if q.get("id") in confirmed_ids]

    # Filter by task type (supports partial matching for umbrella types like "A4")
    if task_type:
        confirmed = [q for q in confirmed if task_type in q.get('task_type', '')]

    # Filter by search term
    if search:
        filtered = []
        for q in confirmed:
            # Search in question text
            if search in q.get('text', '').lower():
                filtered.append(q)
                continue
            # Search in descriptor
            if '_objects' in q and 'descriptor' in q['_objects']:
                if search in q['_objects']['descriptor'].lower():
                    filtered.append(q)
                    continue
        confirmed = filtered

    # Format for display
    formatted = []
    for q in confirmed:
        f = format_question_for_display(q)
        formatted.append(f)

    return jsonify({
        "questions": formatted,
        "count": len(formatted)
    })


# ============================================================================
# Dynamic Question Management
# ============================================================================

@app.route('/api/reload', methods=['POST'])
def reload_questions():
    """Reload questions from the file without restarting the server."""
    global all_questions, skipped_questions

    try:
        # Reload questions from file
        load_questions(questions_file)

        # Clear skipped questions since we have a fresh set
        skipped_questions.clear()

        # Reload audit state too
        auditor.reload_state()

        # Get updated stats
        stats = auditor.get_stats()
        pending_ids = auditor.get_pending_questions(
            [q.get("id") for q in all_questions]
        )

        return jsonify({
            "success": True,
            "message": f"Reloaded {len(all_questions)} questions",
            "stats": {
                "total": len(all_questions),
                "confirmed": stats["confirmed"],
                "flagged": stats["flagged"],
                "pending": len(pending_ids)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/add_questions', methods=['POST'])
def add_questions_api():
    """Add new questions from a JSON payload without restarting the server."""
    global all_questions

    try:
        data = request.get_json()

        # Expect either a list or a dict with "questions" key
        if isinstance(data, list):
            new_questions = data
        elif isinstance(data, dict) and "questions" in data:
            new_questions = data["questions"]
        else:
            return jsonify({
                "success": False,
                "error": "Invalid format. Expected list or dict with 'questions' key"
            }), 400

        # Check for duplicates
        existing_ids = {q["id"] for q in all_questions}
        unique_questions = [q for q in new_questions if q["id"] not in existing_ids]

        if not unique_questions:
            return jsonify({
                "success": False,
                "message": "All questions already exist (duplicates)",
                "added": 0
            })

        # Add to in-memory list
        all_questions.extend(unique_questions)

        # Also append to the file for persistence
        with open(questions_file, 'r') as f:
            file_data = json.load(f)

        file_data["questions"].extend(unique_questions)
        file_data["metadata"]["total_questions"] = len(file_data["questions"])
        file_data["metadata"]["last_modified"] = datetime.now().isoformat()

        # Update task type count
        for q in unique_questions:
            task_type = q.get("task_type", "unknown")
            if task_type in file_data["metadata"]["by_task_type"]:
                file_data["metadata"]["by_task_type"][task_type] += 1
            else:
                file_data["metadata"]["by_task_type"][task_type] = 1

        backup_before_write(questions_file)
        with open(questions_file, 'w') as f:
            json.dump(file_data, f, indent=2)

        return jsonify({
            "success": True,
            "message": f"Added {len(unique_questions)} new questions",
            "added": len(unique_questions),
            "skipped_duplicates": len(new_questions) - len(unique_questions),
            "new_total": len(all_questions)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# Queue Management APIs
# ============================================================================

@app.route('/api/queue/preview', methods=['GET'])
def preview_queue():
    """Preview the next N questions in the pending queue."""
    limit = int(request.args.get('limit', 20))
    task_type_filter = request.args.get('task_type', '')

    # Get pending question IDs
    all_ids = [q.get("id") for q in all_questions]
    pending_ids = auditor.get_pending_questions(all_ids)

    # Filter by task type if specified
    if task_type_filter:
        # Convert short form (A2) to full form (A2_ancestor_verification)
        task_type_mapping = {
            'A1': 'A1_root_classification',
            'A2': 'A2_ancestor_verification',
            'A3': 'A3_sibling_identification',
            'A4': 'A4_path_reconstruction',
            'A5': 'A5_lca_finding',
            'E1': 'E1_similarity_ranking',
            'E2': 'E2_pairwise_comparison',
            'E3': 'E3_odd_one_out',
            'F': 'F_flavor_description'
        }
        full_task_type = task_type_mapping.get(task_type_filter, task_type_filter)
        pending_questions = [q for q in all_questions
                           if q.get("id") in pending_ids
                           and q.get("task_type") == full_task_type]
    else:
        pending_questions = [q for q in all_questions if q.get("id") in pending_ids]

    # Get first N
    preview = pending_questions[:limit]

    # Format for display
    formatted = []
    for i, q in enumerate(preview, 1):
        descriptor = q.get('_objects', {}).get('descriptor', 'N/A')
        formatted.append({
            'position': i,
            'id': q.get('id'),
            'task_type': q.get('task_type'),
            'descriptor': descriptor,
            'text': q.get('text', '')[:100] + ('...' if len(q.get('text', '')) > 100 else '')
        })

    return jsonify({
        'total_pending': len(pending_questions),
        'preview_count': len(formatted),
        'questions': formatted
    })


@app.route('/api/queue/stats', methods=['GET'])
def queue_stats():
    """Get statistics about the queue by task type."""
    # Get all question IDs
    all_ids = [q.get("id") for q in all_questions]

    # Get pending IDs
    pending_ids = set(auditor.get_pending_questions(all_ids))

    # Count by task type
    stats_by_type = {}
    for q in all_questions:
        task_type = q.get('task_type', 'unknown')
        q_id = q.get('id')
        status = auditor.get_status(q_id)

        if task_type not in stats_by_type:
            stats_by_type[task_type] = {
                'total': 0,
                'confirmed': 0,
                'flagged': 0,
                'pending': 0
            }

        stats_by_type[task_type]['total'] += 1
        if status == 'confirmed':
            stats_by_type[task_type]['confirmed'] += 1
        elif status == 'flagged':
            stats_by_type[task_type]['flagged'] += 1
        elif q_id in pending_ids:
            stats_by_type[task_type]['pending'] += 1

    return jsonify({
        'by_task_type': stats_by_type,
        'total_pending': len(pending_ids)
    })


@app.route('/api/queue/prioritize', methods=['POST'])
def prioritize_queue():
    """Prioritize a task type (move to front of queue)."""
    try:
        data = request.get_json()
        task_type = data.get('task_type')

        if not task_type:
            return jsonify({
                'success': False,
                'error': 'Missing task_type parameter'
            }), 400

        # Use the queue manager
        from FlavorGraphTraverser.evaluation.queue_manager import QueueManager

        qm = QueueManager(questions_file)

        # Prioritize the task type
        qm.move_to_front(task_types=[task_type])
        qm.save_queue()

        # Reload questions in auditor
        load_questions(questions_file)
        auditor.reload_state()

        return jsonify({
            'success': True,
            'message': f'Prioritized {task_type} questions'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Results Viewer Routes
# ============================================================================

@app.route('/results')
def results_page():
    """Results viewer page."""
    return render_template('auditor_unified.html', mode='results')


@app.route('/api/results')
def get_results():
    """Get evaluation results with optional filtering."""
    maybe_reload_results()
    if results_data is None:
        return jsonify({"error": "No results file loaded. Start the server with --results <path>."}), 404

    results = results_data.get("results", [])

    # Apply filters
    model_filter = request.args.get('model', '')
    condition_filter = request.args.get('condition', '')
    task_type_filter = request.args.get('task_type', '')
    status_filter = request.args.get('status', '')  # correct / wrong / parse_error / api_error
    search = request.args.get('search', '').lower()

    filtered = results
    if model_filter:
        filtered = [r for r in filtered if r.get('model') == model_filter]
    if condition_filter:
        filtered = [r for r in filtered if r.get('condition') == condition_filter]
    if task_type_filter:
        filtered = [r for r in filtered if task_type_filter in r.get('task_type', '')]
    if status_filter == 'correct':
        filtered = [r for r in filtered if r.get('is_correct')]
    elif status_filter == 'wrong':
        filtered = [r for r in filtered if not r.get('is_correct') and r.get('status') == 'success']
    elif status_filter in ('parse_error', 'api_error', 'tool_error'):
        filtered = [r for r in filtered if r.get('status') == status_filter]
    if search:
        filtered = [r for r in filtered if search in r.get('question_id', '').lower()]

    # Build summary rows (no conversation history — too large for list view)
    rows = []
    for r in filtered:
        metrics = r.get('metrics', {})
        rows.append({
            'question_id': r.get('question_id'),
            'model': r.get('model'),
            'condition': r.get('condition'),
            'task_type': r.get('task_type', ''),
            'is_correct': r.get('is_correct'),
            'status': r.get('status'),
            'model_answer': r.get('model_answer'),
            'correct_answer': r.get('correct_answer'),
            'judge_score': r.get('judge_score'),
            'judge_scores': r.get('judge_scores', {}),
            'score': r.get('score', 0.0),
            'reasoning_calls': metrics.get('reasoning_calls', 0),
            'validation_calls': metrics.get('validation_calls', 0),
            'total_turns': metrics.get('total_turns', 0),
            'total_tokens': metrics.get('total_tokens', 0),
            'latency_seconds': r.get('latency_seconds', 0),
        })

    # Compute quick stats over filtered set
    total = len(rows)
    n_correct = sum(1 for r in rows if r['is_correct'])
    f_scores = [r['judge_score'] for r in rows if r['judge_score'] is not None]

    # Enumerate unique models/conditions for filter dropdowns
    all_models = sorted({r.get('model', '') for r in results})
    all_conditions = sorted({r.get('condition', '') for r in results})
    all_task_types = sorted({r.get('task_type', '') for r in results})

    # Score aggregation:
    # Exclude rows with status='no_judge' from score aggregates because their
    # score=0 reflects the absence of a judge, not a model failure. Including
    # them would understate F-category performance.
    SCORABLE_STATUSES = {'success', 'parse_error', 'api_error', 'tool_error', 'judge_parse_error'}
    scorable_rows = [r for r in rows if r['status'] in SCORABLE_STATUSES]

    from collections import defaultdict
    by_task = defaultdict(list)
    for r in scorable_rows:
        if r.get('task_type'):
            by_task[r['task_type']].append(r.get('score', 0.0))
    cat_avgs = [sum(scores) / len(scores) for scores in by_task.values() if scores]
    macro_score = round(sum(cat_avgs) / len(cat_avgs), 4) if cat_avgs else 0
    micro_score = (
        round(sum(r.get('score', 0.0) for r in scorable_rows) / len(scorable_rows), 4)
        if scorable_rows else 0
    )
    n_unscored = total - len(scorable_rows)

    return jsonify({
        'run_status': results_data.get('run_status', 'complete'),
        'results': rows,
        'total': total,
        'n_correct': n_correct,
        'n_scorable': len(scorable_rows),
        'n_unscored': n_unscored,  # rows excluded from score aggregation (no_judge)
        'accuracy': round(n_correct / total, 4) if total else 0,
        'micro_score': micro_score,
        'macro_score': macro_score,
        'avg_judge_score': round(sum(f_scores) / len(f_scores), 2) if f_scores else None,
        'filters': {
            'models': all_models,
            'conditions': all_conditions,
            'task_types': all_task_types,
        }
    })


@app.route('/api/results/summary')
def get_results_summary():
    """Get full summary statistics from results file."""
    maybe_reload_results()
    if results_data is None:
        return jsonify({"error": "No results file loaded."}), 404
    return jsonify(results_data.get('summary', {}))


@app.route('/api/progress')
def get_progress():
    """Get per-model×condition evaluation progress.

    Counts unique question IDs directly from cache files so progress
    updates per-question (not just when a full condition batch finishes).
    Deduplicates across runs: newest cache file wins for the same key.
    """
    import glob as _glob

    # Scan all cache directories: results/*/cache and results/*/*/cache
    # Cache layout: <cache_root>/<provider>/<model>/<condition>/<qid>.json
    seen: dict = {}  # (model, condition, qid) → mtime

    for pattern in ["results/*/cache", "results/*/*/cache"]:
        for cache_root in _glob.glob(pattern):
            for qfile in _glob.glob(f"{cache_root}/**/*.json", recursive=True):
                try:
                    rel = Path(qfile).relative_to(cache_root)
                    parts = rel.parts  # e.g. ('anthropic', 'claude-sonnet-4.6', 'no_tool', 'A1_xxx.json')
                    if len(parts) < 3:
                        continue
                    qid = parts[-1].replace(".json", "")
                    condition = parts[-2]
                    model = "/".join(parts[:-2])
                    key = (model, condition, qid)
                    mtime = os.path.getmtime(qfile)
                    if key not in seen or seen[key] < mtime:
                        seen[key] = mtime
                except Exception:
                    continue

    # Count unique questions per model×condition
    counts: dict = {}
    for (model, condition, _) in seen:
        k = f"{model}|{condition}"
        counts[k] = counts.get(k, 0) + 1

    # Total from benchmark file
    benchmark_file = project_root / "data" / "questions" / "benchmark_questions.json"
    try:
        with open(benchmark_file) as f:
            bdata = json.load(f)
        bqs = bdata.get("questions", bdata) if isinstance(bdata, dict) else bdata
        total_questions = len([q for q in bqs if q.get("status") != "rejected"])
    except Exception:
        total_questions = max(counts.values()) if counts else 0

    run_status = results_data.get("run_status", "complete") if results_data else "unknown"

    return jsonify({
        "total_questions": total_questions,
        "by_model_condition": counts,
        "run_status": run_status,
    })


@app.route('/api/results/<path:question_id>')
def get_result_detail(question_id):
    """Get full result detail including conversation history."""
    maybe_reload_results()
    if results_data is None:
        return jsonify({"error": "No results file loaded."}), 404

    model = request.args.get('model', '')
    condition = request.args.get('condition', '')

    for r in results_data.get('results', []):
        if r.get('question_id') == question_id:
            if model and r.get('model') != model:
                continue
            if condition and r.get('condition') != condition:
                continue
            return jsonify(r)

    return jsonify({"error": f"Result not found: {question_id}"}), 404


# ============================================================================
# Main
# ============================================================================

def main():
    """Main entry point."""
    global auditor

    # Parse arguments
    questions_path = "data/questions/all_questions_system.json"
    results_path = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--results' and i + 1 < len(args):
            results_path = args[i + 1]
            i += 2
        elif not args[i].startswith('--'):
            questions_path = args[i]
            i += 1
        else:
            i += 1

    print(f"Loading questions from: {questions_path}")

    # Initialize auditor
    auditor = QuestionAuditor()
    load_questions(questions_path)

    print(f"Loaded {len(all_questions)} questions")
    print()

    # Show status
    stats = auditor.get_stats()
    print("Audit Status:")
    print(f"  Confirmed: {stats['confirmed']}")
    print(f"  Flagged: {stats['flagged']}")
    print(f"  Pending: {len(all_questions) - stats['total_reviewed']}")
    print()

    # Auto-discover most recent results if none specified
    if results_path is None:
        candidates = sorted(
            Path(project_root / "results").glob("*/results.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if candidates:
            results_path = str(candidates[0])
            print(f"Auto-discovered results: {results_path}")

    # Load results if available
    if results_path:
        try:
            load_results(results_path)
            n_results = len(results_data.get('results', []))
            print(f"Loaded {n_results} evaluation results from: {results_path}")
        except Exception as e:
            print(f"Warning: Could not load results file: {e}")
    print()

    print("=" * 70)
    print("Unified Question Auditor")
    print("=" * 70)
    print()
    print("Open in browser:")
    print("  Audit mode:   http://localhost:5000/audit")
    print("  Review mode:  http://localhost:5000/review")
    if results_path:
        print("  Results mode: http://localhost:5000/results")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()

    # Run Flask app — bind to localhost only, debug off
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
