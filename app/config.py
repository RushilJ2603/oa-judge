"""Central configuration for OA Judge.

Resolution order for every setting: environment variable → config.local.json (gitignored,
per-machine) → built-in default. Keeping this in one module means Phase 6 (hosting) can point
the app at a different problems checkout, database, or bind address without touching call sites.

The most important knob is PROBLEMS_DIR. The question bank is a *separate* git repository
(`oa-problems`) cloned into `oa-judge/problems/`. The app only reads it, so the two repos update
independently: `git pull` in the app never conflicts with `git pull` in the problems bank.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                     # oa-judge/
_LOCAL_PATH = os.path.join(ROOT, "config.local.json")

# Cache the per-machine overrides file once.
try:
    with open(_LOCAL_PATH, encoding="utf-8") as _f:
        _LOCAL = json.load(_f)
except (FileNotFoundError, json.JSONDecodeError, OSError):
    _LOCAL = {}


def get(key: str, default=None):
    """env (OAJ_<KEY>) wins, then config.local.json, then the passed default."""
    env = os.environ.get("OAJ_" + key.upper())
    if env is not None:
        return env
    if key in _LOCAL:
        return _LOCAL[key]
    return default


# --- resolved settings ---------------------------------------------------------
# Problems live in oa-judge/problems by default (the oa-problems clone). Override with
# OAJ_PROBLEMS_DIR or {"problems_dir": "..."} in config.local.json.
PROBLEMS_DIR = os.path.abspath(get("problems_dir", os.path.join(ROOT, "problems")))

# SQLite database (personal data; gitignored). db.py also honours OAJ_DB directly.
DB_PATH = os.path.abspath(get("db", os.path.join(HERE, "data", "judge.db")))

# Network bind.
HOST = get("host", "127.0.0.1")
PORT = int(get("port", 5137))

# Identity stamped onto problems you author + publish (Phase 5). Falls back to the OS user.
AUTHOR = get("author", os.environ.get("USER") or os.environ.get("USERNAME") or "anon")
