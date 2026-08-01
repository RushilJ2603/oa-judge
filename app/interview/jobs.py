"""Job queue between the browser and the local agy worker, plus worker liveness.

Why a queue at all: the worker lives on a laptop inside WSL and can vanish mid-interview (WSL
stopped, machine asleep, reboot). Session state therefore lives here, in SQLite on the server, and a
turn is just a row. A worker that dies loses nothing — the lease expires and the turn is re-offered.

Quotas live here too. Friends share the host's Gemini subscription, so a per-user daily cap and a
small concurrency limit keep one person from draining it or fork-bombing the laptop.
"""
import datetime
import json

import db

LEASE_SECONDS = 300
MAX_ATTEMPTS = 3
MAX_CONCURRENT = 2            # simultaneous agy spawns on one laptop
DAILY_PER_USER = 120          # turns/day/user
ONLINE_WINDOW_S = 60          # a beat newer than this means "Interviewer online"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt=None):
    return (dt or _now()).isoformat(timespec="seconds")


# ------------------------------------------------------------------ enqueue / poll (browser side)
def enqueue(user_id: int, session_id: int, prompt: str, kind: str = "turn") -> dict:
    conn = db.connect()
    if used_today(user_id) >= DAILY_PER_USER:
        return {"error": "daily interview limit reached"}
    n = conn.execute("SELECT COUNT(*) AS n FROM interview_job WHERE status='queued'").fetchone()["n"]
    if n > 50:
        return {"error": "queue is busy, try again shortly"}
    cur = conn.execute(
        "INSERT INTO interview_job (session_id, user_id, kind, payload_json, status, created_at, "
        "updated_at) VALUES (?,?,?,?,'queued',?,?)",
        (session_id, user_id, kind, json.dumps({"prompt": prompt}), _iso(), _iso()))
    conn.commit()
    return {"job_id": cur.lastrowid}


def poll(user_id: int, job_id: int) -> dict:
    row = db.connect().execute(
        "SELECT status, result_json, error FROM interview_job WHERE id=? AND user_id=?",
        (job_id, user_id)).fetchone()                 # scoped: you can only poll your own job
    if not row:
        return {"status": "unknown"}
    out = {"status": row["status"]}
    if row["error"]:
        out["error"] = row["error"]
    if row["result_json"]:
        try:
            out["output"] = json.loads(row["result_json"]).get("output", "")
        except Exception:
            out["output"] = ""
    return out


def used_today(user_id: int) -> int:
    day = _now().strftime("%Y-%m-%d")
    return db.connect().execute(
        "SELECT COUNT(*) AS n FROM interview_job WHERE user_id=? AND created_at LIKE ?",
        (user_id, day + "%")).fetchone()["n"]


# ------------------------------------------------------------------ lease / result (worker side)
def lease(worker_id: str, version: str = "") -> dict | None:
    """Hand the worker one job and mark it leased. Also records the heartbeat."""
    conn = db.connect()
    beat(worker_id, version)
    busy = conn.execute(
        "SELECT COUNT(*) AS n FROM interview_job WHERE status='leased' AND lease_until > ?",
        (_iso(),)).fetchone()["n"]
    if busy >= MAX_CONCURRENT:
        return None
    # Reclaim anything whose lease expired (worker died mid-turn) before taking new work.
    conn.execute("UPDATE interview_job SET status='queued' WHERE status='leased' AND lease_until <= ?",
                 (_iso(),))
    conn.commit()
    row = conn.execute(
        "SELECT id, payload_json, attempts FROM interview_job WHERE status='queued' "
        "ORDER BY created_at LIMIT 1").fetchone()
    if not row:
        return None
    if row["attempts"] >= MAX_ATTEMPTS:
        conn.execute("UPDATE interview_job SET status='failed', error='max attempts', updated_at=? "
                     "WHERE id=?", (_iso(), row["id"]))
        conn.commit()
        return None
    until = _iso(_now() + datetime.timedelta(seconds=LEASE_SECONDS))
    conn.execute("UPDATE interview_job SET status='leased', attempts=attempts+1, lease_until=?, "
                 "updated_at=? WHERE id=?", (until, _iso(), row["id"]))
    conn.commit()
    payload = json.loads(row["payload_json"])
    return {"job_id": row["id"], "prompt": payload.get("prompt", "")}


def complete(job_id: int, output: str = "", error: str = "") -> None:
    conn = db.connect()
    if error:
        # Put it back for another attempt; the lease/attempt cap stops infinite loops.
        conn.execute("UPDATE interview_job SET status='queued', error=?, lease_until=NULL, "
                     "updated_at=? WHERE id=?", (error[:400], _iso(), job_id))
    else:
        conn.execute("UPDATE interview_job SET status='done', result_json=?, error=NULL, "
                     "updated_at=? WHERE id=?",
                     (json.dumps({"output": output}), _iso(), job_id))
    conn.commit()


def job_owner(job_id: int) -> tuple[int, int] | None:
    row = db.connect().execute("SELECT user_id, session_id FROM interview_job WHERE id=?",
                               (job_id,)).fetchone()
    return (row["user_id"], row["session_id"]) if row else None


# ------------------------------------------------------------------ liveness (the host toggle)
def beat(worker_id: str, version: str = "") -> None:
    db.connect().execute(
        "INSERT OR REPLACE INTO worker_beat (worker_id, last_seen, version) VALUES (?,?,?)",
        (worker_id, _iso(), version))
    db.connect().commit()


def online() -> bool:
    """True when a worker has beaten recently. This IS the host toggle — no separate flag."""
    cutoff = _iso(_now() - datetime.timedelta(seconds=ONLINE_WINDOW_S))
    row = db.connect().execute(
        "SELECT COUNT(*) AS n FROM worker_beat WHERE last_seen > ?", (cutoff,)).fetchone()
    return bool(row["n"])
