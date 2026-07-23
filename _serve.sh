#!/usr/bin/env bash
# WSL-side entry point for the Windows launcher (launch.bat / OA Judge.lnk).
# Kept as its own file so the .bat can pass one path with no embedded quotes.
cd "$(dirname "$0")" || exit 1
export OAJ_PORT="${OAJ_PORT:-5137}"
echo "Starting OA Judge on http://127.0.0.1:${OAJ_PORT}  (close this window to stop)"
exec python3 app/server.py
