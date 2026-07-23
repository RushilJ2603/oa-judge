#!/usr/bin/env bash
# OA Judge — one-command setup for a fresh machine.
#
#   git clone <oa-judge-url> && cd oa-judge && ./setup.sh
#
# Clones the shared problem bank, checks the toolchain, initialises the local database, and
# prints how to launch. Safe to re-run: it updates an existing checkout instead of failing.
set -euo pipefail
cd "$(dirname "$0")"

# The problem bank is a SEPARATE repo cloned into ./problems. Override with OA_PROBLEMS_REPO
# if you fork it. Default owner is inferred from the oa-judge 'origin' remote.
default_owner() {
  git remote get-url origin 2>/dev/null | sed -nE 's#.*github\.com[:/]+([^/]+)/.*#\1#p'
}
OWNER="${OA_PROBLEMS_OWNER:-$(default_owner)}"
OA_PROBLEMS_REPO="${OA_PROBLEMS_REPO:-https://github.com/${OWNER:-CHANGEME}/oa-problems.git}"

echo "── OA Judge setup ─────────────────────────────────────────"

# 1. Toolchain checks (warn, don't hard-fail, so a partial setup still completes).
have() { command -v "$1" >/dev/null 2>&1; }
PY=python3
if ! have "$PY"; then echo "ERROR: python3 not found — install Python 3.10+ and re-run."; exit 1; fi
echo "✓ python3: $($PY --version 2>&1)"

if ! "$PY" -c 'import flask' 2>/dev/null; then
  echo "… installing Flask (pip)"
  "$PY" -m pip install --user flask 2>/dev/null || \
    "$PY" -m pip install --break-system-packages flask 2>/dev/null || {
      echo "  couldn't auto-install Flask. Install it manually:  $PY -m pip install flask"; }
fi
"$PY" -c 'import flask' 2>/dev/null && echo "✓ flask installed"

have g++ && echo "✓ g++: $(g++ --version | head -1)" || \
  echo "⚠ g++ not found — C++ problems won't run until you install it (e.g. sudo apt install g++)."
have git || { echo "ERROR: git is required for the shared problem bank."; exit 1; }

# 2. The problem bank.
if [ -d problems/.git ]; then
  echo "… updating existing problem bank"
  git -C problems pull --ff-only || echo "⚠ could not fast-forward problems/ (local changes?)"
elif [ -d problems ] && [ -n "$(ls -A problems 2>/dev/null)" ]; then
  echo "✓ problems/ already present (not a git checkout — leaving as-is)"
else
  echo "… cloning problem bank from $OA_PROBLEMS_REPO"
  if ! git clone "$OA_PROBLEMS_REPO" problems; then
    echo "⚠ could not clone the bank. Set OA_PROBLEMS_REPO to the right URL and re-run,"
    echo "  or create problems/ manually. The app runs fine with a local-only bank."
  fi
fi
[ -d problems ] && echo "✓ problems: $(ls -d problems/*/ 2>/dev/null | wc -l) packages"

# 3. Initialise the local database (migrations run on first connect).
"$PY" - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "app"))
import db
db.connect()
print("✓ database ready at", db.DB_PATH)
PYEOF

# 4. Optional: a faster WSGI server. Not required for single-user use.
"$PY" -c 'import waitress' 2>/dev/null && echo "✓ waitress present (used automatically)" || \
  echo "· (optional) 'pip install waitress' for a sturdier server"

PORT="${OAJ_PORT:-5137}"
echo "───────────────────────────────────────────────────────────"
echo "Setup complete. Launch with:"
echo "    ./start.sh        # or:  python3 app/server.py"
echo "Then open  http://127.0.0.1:${PORT}"
