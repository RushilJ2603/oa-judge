"""Attempt log persisted to app/data/history.json."""
import json
import os
import threading
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
_lock = threading.Lock()


def _load() -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def record(problem_id, language, mode, verdict, passed, total, duration_s=None):
    with _lock:
        attempts = _load()
        attempts.append({
            "problem_id": problem_id, "language": language, "mode": mode,
            "verdict": verdict, "passed": passed, "total": total,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "duration_s": duration_s,
        })
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(attempts, f, indent=1)


def solved_ids() -> set[str]:
    return {a["problem_id"] for a in _load() if a["verdict"] == "AC"}


def attempts(problem_id=None) -> list[dict]:
    items = _load()
    if problem_id:
        items = [a for a in items if a["problem_id"] == problem_id]
    return list(reversed(items))


def revisit_list(all_ids: list[str]) -> list[str]:
    """Problems that were attempted-but-never-AC'd, plus never-attempted ones."""
    solved = solved_ids()
    attempted = {a["problem_id"] for a in _load()}
    failed = [pid for pid in all_ids if pid in attempted and pid not in solved]
    untouched = [pid for pid in all_ids if pid not in attempted]
    return failed + untouched
