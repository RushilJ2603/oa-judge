#!/usr/bin/env bash
# OA Judge launcher (Linux / WSL / macOS). Starts the server and opens the browser.
set -e
cd "$(dirname "$0")"

PORT="${OAJ_PORT:-5137}"

# Pick a python with flask available.
PY="python3"
if ! "$PY" -c "import flask" 2>/dev/null; then
  echo "Flask is not installed for $PY."
  echo "Install it with:  $PY -m pip install flask"
  exit 1
fi

# Verify g++ is present (C++ problems need it).
if ! command -v g++ >/dev/null 2>&1; then
  echo "WARNING: g++ not found on PATH — C++ problems will not run."
fi

URL="http://127.0.0.1:${PORT}"
echo "Starting OA Judge on ${URL} ..."

# Open the browser shortly after the server comes up (best-effort, non-fatal).
( sleep 1.5
  if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  elif command -v open >/dev/null 2>&1; then open "$URL"
  elif command -v wslview >/dev/null 2>&1; then wslview "$URL"
  fi ) >/dev/null 2>&1 &

exec env OAJ_PORT="$PORT" "$PY" app/server.py
