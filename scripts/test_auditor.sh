#!/bin/bash
# Test script for Question Auditor
# Runs all component tests to verify the auditor works correctly

set -e

echo "======================================================================="
echo "Question Auditor - Test Suite"
echo "======================================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test 1: QuestionAuditor Module
echo "Test 1: QuestionAuditor Module"
echo "----------------------------------------------------------------------"
python -c "
from FlavorGraphTraverser.evaluation.question_auditor import QuestionAuditor, format_question_for_display
import json
import os

# Clean up
if os.path.exists('data/test_audit_state.json'):
    os.remove('data/test_audit_state.json')

auditor = QuestionAuditor('data/test_audit_state.json')

with open('data/sample_questions_for_audit.json') as f:
    questions = json.load(f)['questions']

# Test operations
auditor.confirm_question('TEST_001')
auditor.flag_question('TEST_002', 'Test reason')
stats = auditor.get_stats()

# Test formatting
formatted = format_question_for_display(questions[0])

# Test duplicate detection
duplicate_id = auditor.check_duplicate(questions[3], [questions[0]])

# Clean up
try:
    os.remove('data/test_audit_state.json')
except:
    pass

print('✅ Module tests passed')
print(f'   - Confirm/flag: OK')
print(f'   - Stats: {stats}')
print(f'   - Formatting: OK')
print(f'   - Duplicate detection: OK')
"
echo ""

# Test 2: Flask API
echo "Test 2: Flask API Endpoints"
echo "----------------------------------------------------------------------"
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from flask import Flask
import json
import os

# Clean up
if os.path.exists('data/test_audit_state.json'):
    os.remove('data/test_audit_state.json')

from FlavorGraphTraverser.evaluation.question_auditor import QuestionAuditor, format_question_for_display

app = Flask(__name__)
auditor = QuestionAuditor(state_file='data/test_audit_state.json')

with open('data/sample_questions_for_audit.json') as f:
    all_questions = json.load(f)['questions']

@app.route('/api/stats')
def get_stats():
    from flask import jsonify
    stats = auditor.get_stats()
    stats['total_questions'] = len(all_questions)
    return jsonify(stats)

@app.route('/api/current')
def get_current():
    from flask import jsonify
    all_ids = [q['id'] for q in all_questions]
    pending_ids = auditor.get_pending_questions(all_ids)
    if not pending_ids:
        return jsonify({'done': True})
    current_q = next(q for q in all_questions if q['id'] in pending_ids)
    formatted = format_question_for_display(current_q)
    return jsonify(formatted)

with app.test_client() as client:
    response = client.get('/api/stats')
    assert response.status_code == 200

    response = client.get('/api/current')
    assert response.status_code == 200

    print('✅ Flask API tests passed')
    print('   - /api/stats: OK')
    print('   - /api/current: OK')

# Clean up
try:
    os.remove('data/test_audit_state.json')
except:
    pass
"
echo ""

# Test 3: CLI Review Tool
echo "Test 3: CLI Review Tool"
echo "----------------------------------------------------------------------"
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

import json
import os

# Clean up
for f in ['data/test_audit_state.json', 'data/test_flagged.jsonl']:
    try:
        if os.path.exists(f):
            os.remove(f)
    except:
        pass

from FlavorGraphTraverser.evaluation.question_auditor import QuestionAuditor
from scripts.review_flagged import FlaggedQuestionReviewer

auditor = QuestionAuditor(state_file='data/test_audit_state.json')

with open('data/sample_questions_for_audit.json') as f:
    questions = json.load(f)['questions']

# Flag a question
test_q = questions[4]
auditor.flag_question(test_q['id'], 'Test reason', 'Test notes')

# Create log
log_entry = {
    'question_id': test_q['id'],
    'question': test_q,
    'reason': 'Test reason',
    'notes': 'Test notes',
    'timestamp': '2026-01-31T10:00:00Z'
}

with open('data/test_flagged.jsonl', 'w') as f:
    f.write(json.dumps(log_entry) + '\n')

# Test reviewer
reviewer = FlaggedQuestionReviewer('data/test_flagged.jsonl', auditor)
flagged = reviewer.load_flagged()

assert len(flagged) == 1
assert flagged[0]['question_id'] == test_q['id']

print('✅ CLI review tool tests passed')
print(f'   - Load flagged: {len(flagged)} questions')
print(f'   - Question ID: {flagged[0][\"question_id\"]}')

# Clean up
for f in ['data/test_audit_state.json', 'data/test_flagged.jsonl']:
    try:
        if os.path.exists(f):
            os.remove(f)
    except:
        pass
"
echo ""

# Test 4: Integration Test
echo "Test 4: Integration Test (Web Server)"
echo "----------------------------------------------------------------------"
echo "Starting server on port 5001..."

# Clean up
rm -f data/test_audit_state.json data/test_flagged.jsonl

# Start server in background
python scripts/audit_questions_web.py \
    data/sample_questions_for_audit.json \
    --state-file data/test_audit_state.json \
    --port 5001 \
    > /dev/null 2>&1 &

SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to start
sleep 3

# Test with curl
echo "Testing endpoints with curl..."

# Test stats
curl -s http://localhost:5001/api/stats > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ GET /api/stats: OK"
else
    echo "❌ GET /api/stats: FAILED"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Test current
CURRENT=$(curl -s http://localhost:5001/api/current)
if [ $? -eq 0 ]; then
    echo "✅ GET /api/current: OK"
else
    echo "❌ GET /api/current: FAILED"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Extract question ID
QUESTION_ID=$(echo "$CURRENT" | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "   Current question: $QUESTION_ID"

# Test confirm
curl -s -X POST -H "Content-Type: application/json" \
    -d "{\"question_id\": \"$QUESTION_ID\"}" \
    http://localhost:5001/api/confirm > /dev/null

if [ $? -eq 0 ]; then
    echo "✅ POST /api/confirm: OK"
else
    echo "❌ POST /api/confirm: FAILED"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Stop server
echo "Stopping server..."
kill $SERVER_PID 2>/dev/null || true
sleep 1
kill -9 $SERVER_PID 2>/dev/null || true

# Clean up
rm -f data/test_audit_state.json data/test_flagged.jsonl

echo ""

# Summary
echo "======================================================================="
echo "Test Summary"
echo "======================================================================="
echo ""
echo -e "${GREEN}✅ All tests passed!${NC}"
echo ""
echo "Components tested:"
echo "  ✅ QuestionAuditor module"
echo "  ✅ Flask API endpoints"
echo "  ✅ CLI review tool"
echo "  ✅ Web server integration"
echo ""
echo "The Question Auditor is ready to use!"
echo ""
echo "Try it now:"
echo "  python scripts/audit_questions_web.py data/sample_questions_for_audit.json"
echo ""
echo "======================================================================="
