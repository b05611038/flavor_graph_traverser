#!/bin/bash
# Start the unified question auditor
# Stops old processes and starts the new unified interface

echo "🔍 Starting Unified Question Auditor"
echo "===================================="
echo

# Stop old processes on ports 5000 and 5001
echo "Stopping old processes..."
lsof -ti:5000,5001 | xargs kill -9 2>/dev/null
sleep 1

# Start unified auditor
echo "Starting unified auditor on port 5000..."
python scripts/question_auditor_unified.py data/questions/all_questions_system.json
