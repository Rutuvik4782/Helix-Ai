#!/bin/bash
set -e

echo "Starting Helix AI Legacy Python Modernizer..."

PYTHON_BIN="${PYTHON_BIN:-./.venv312/bin/python3}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="./.venv/bin/python3"
fi

export ML_MODEL_ENABLED="${ML_MODEL_ENABLED:-true}"
export ML_MODEL_ADAPTER_PATH="${ML_MODEL_ADAPTER_PATH:-ml/models/nebula-modernizer-qwen25-1.5b}"
export ML_MODEL_BASE="${ML_MODEL_BASE:-Qwen/Qwen2.5-Coder-1.5B-Instruct}"

nohup "$PYTHON_BIN" -m uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
echo $! > server.pid
echo "Server started with PID $(cat server.pid)"
echo "ML_MODEL_ENABLED=$ML_MODEL_ENABLED"
