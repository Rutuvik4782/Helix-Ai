#!/bin/bash
echo "Starting Helix AI Legacy Python Modernizer..."
# Use python3 -m uvicorn to ensure we use the installed module
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > server.log 2>&1 &
echo $! > server.pid
echo "Server started with PID $(cat server.pid)"
