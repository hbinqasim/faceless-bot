#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
PROJECT_DIR="/Users/hbinqasim/Projects/faceless-bot"
PYTHON="$PROJECT_DIR/venv/bin/python"

cd "$PROJECT_DIR"

mkdir -p logs

echo "------------------------------" >> logs/scheduler.log
echo "Run started: $(date)" >> logs/scheduler.log

"$PYTHON" produce_and_upload.py >> logs/scheduler.log 2>&1

echo "Run finished: $(date)" >> logs/scheduler.log