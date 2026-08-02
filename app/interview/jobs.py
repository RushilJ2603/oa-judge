"""Job queue between the browser and the local agy worker, plus worker liveness.

Why a queue at all: the worker lives on a laptop inside WSL and can vanish mid-interview (WSL
stopped, machine asleep, reboot). Session state therefore lives here, in SQLite on the server, and a
turn is just a row. A worker that dies loses nothing — the lease expires and the turn is re-offered.

Quotas live here too. Friends share the host's Gemini subscription, so a per-user daily cap and a
small concurrency limit keep one person from draining it or fork-bombing the laptop.
"""
import datetime
import os
import json
import time

import db

LEASE_SECONDS = 300
MAX_ATTEMPTS = 3
# Simultaneous agy spawns. Sized for a shared host: with ~15s per turn, N=6 clears roughly 24
# turns/minute, so a room of 10-16 people each answering every 30-60s never queues. Raise via
# OAJ_INTERVIEW_CONCURRENCY if the host machine has headroom; each spawn is a CLI + network wait,
# not CPU-bound, so it scales further than core count suggests.
MAX_CONCURRENT = int(os.environ.get("OAJ_INTERVIEW_CONCURRENCY", "6"))
DAILY_PER_USER = 120          # turns/day/user
MAX_QUEUE = 200               # backstop; well above 16 users' in-flight turns
ONLINE_WINDOW_S = 60          # a beat newer than this means "Interviewer online"
# How long after its last turn a session still counts as LIVE. Long enough to cover someone thinking
# hard about a system-design question, short enough that an interview abandoned mid-way stops holding
# the worker — and therefore the Fly machine — awake.
LIVE_WINDOW_S = 1800


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt=None):
    return (dt or _now()).isoformat(timespec="seconds")


# ------------------------------------------------------------------ enqueue / poll (browser side)
def enqueue(user_id: int, session_id: int, prompt, kind: str = "turn") -> dict:
    """`prompt` is either a flat string or a payload dict {prompt, system, history}.

    Both shapes are stored, because both are needed: the API path answers from the conversational
    (system + history) shape, and the agy fallback can only take the flat string. Whichever worker
    picks the job up finds what it can use.
    """
    conn = db.connect()
    if used_today(user_id) >= DAILY_PER_USER:
        return {"error": "daily interview limit reached"}
    n = conn.execute("SELECT COUNT(*) AS n FROM interview_job WHERE status='queued'").fetchone()["n"]
    if n > MAX_QUEUE:
        return {"error": "queue is busy, try again shortly"}
    cur = conn.execute(
        "INSERT INTO interview_job (session_id, user_id, kind, payload_json, status, created_at, "
        "updated_at) VALUES (?,?,?,?,'queued',?,?)",
        (session_id, user_id, kind,
         json.dumps(prompt if isinstance(prompt, dict) else {"prompt": prompt}), _iso(), _iso()))
    conn.commit()
    return {"job_id": cur.lastrowid}


def poll(user_id: int, job_id: int) -> dict:
    row = db.connect().execute(
        "SELECT status, result_json, error FROM interview_job WHERE id=? AND user_id=?",
        (job_id, user_id)).fetchone()                 # scoped: you can only poll your own job
    if not row:
        return {"status": "unknown"}
    out = {"status": row["status"]}
    # `error` is TERMINAL — the client stops polling and prints it into the transcript. A job that is
    # merely waiting for a rate limit to lift is still queued and will be answered, so its reason is
    # a `note` instead. Reporting it as an error meant a 429 looked like a dead interview when it was
    # only a pause.
    if row["error"]:
        if row["status"] == "failed":
            out["error"] = row["error"]
        else:
            out["note"] = row["error"]
            out["retrying"] = True
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
def sessions_live() -> bool:
    """Is anyone actually mid-interview right now?

    Used to decide whether the worker should stay hot. Derived from the newest turn rather than from
    `started_at`, so a session someone is still thinking about counts as live while one abandoned an
    hour ago does not.
    """
    cutoff = _iso(_now() - datetime.timedelta(seconds=LIVE_WINDOW_S))
    return db.connect().execute(
        "SELECT 1 FROM interview_session s WHERE s.status='active' AND "
        "COALESCE((SELECT MAX(t.created_at) FROM interview_turn t WHERE t.session_id = s.id), "
        "         s.started_at) > ? LIMIT 1", (cutoff,)).fetchone() is not None


def _queued_waiting() -> bool:
    """Cheap read: is there a job to take? Keeps the wait loop's tick nearly free, so it can run
    often enough that pickup is effectively instant."""
    return db.connect().execute(
        "SELECT 1 FROM interview_job WHERE status='queued' LIMIT 1").fetchone() is not None


WAIT_TICK_S = 0.15
WAIT_MAX_S = 25.0             # below any sane proxy idle timeout, above a comfortable poll period


def lease_waiting(worker_id: str, version: str = "", max_wait: float = 0.0) -> dict:
    """Lease a job, holding the request open until one appears.

    This replaced a client-side poll that backed off geometrically while idle. The backoff existed to
    let the Fly machine sleep, but it had a perverse effect during a real interview: the candidate
    spends a minute or two thinking, the worker sees no work and eases out to a 20s poll, and their
    NEXT answer then waits up to 20 seconds just to be noticed — often longer than the model call
    itself. Holding the connection instead makes pickup immediate and sends *fewer* requests than
    polling did.
    """
    job = lease(worker_id, version)                # also beats + reclaims expired leases
    if job:
        return {**job, "live": True}
    if max_wait <= 0:
        return {"live": sessions_live()}
    deadline = time.monotonic() + min(max_wait, WAIT_MAX_S)
    last_beat = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(WAIT_TICK_S)
        if _queued_waiting():
            job = lease(worker_id, version)
            if job:
                return {**job, "live": True}
        elif time.monotonic() - last_beat >= ONLINE_WINDOW_S / 3:
            beat(worker_id, version)               # "Interviewer online" must not lapse mid-hold
            last_beat = time.monotonic()
    return {"live": sessions_live()}


def lease(worker_id: str, version: str = "", heartbeat: bool = True) -> dict | None:
    """Hand the caller one job and mark it leased. Also records the heartbeat.

    Safe under concurrency: a multi-threaded worker (needed to serve 10-16 people at once) issues
    several leases simultaneously. Selecting a row and then updating it would let two threads claim
    the SAME turn and run it twice, so the claim is a single conditional UPDATE and only the thread
    whose rowcount is 1 gets the job.
    """
    conn = db.connect()
    if heartbeat:
        # The in-process cloud answerer passes heartbeat=False: worker_beat means "a HOST machine is
        # up", and beating here would make the UI claim agy is available when only the API is.
        beat(worker_id, version)
    now = _iso()
    # Reclaim anything whose lease expired (worker died mid-turn) before counting or taking work.
    conn.execute("UPDATE interview_job SET status='queued' WHERE status='leased' AND lease_until <= ?",
                 (now,))
    conn.commit()
    busy = conn.execute(
        "SELECT COUNT(*) AS n FROM interview_job WHERE status='leased' AND lease_until > ?",
        (now,)).fetchone()["n"]
    if busy >= MAX_CONCURRENT:
        return None

    until = _iso(_now() + datetime.timedelta(seconds=LEASE_SECONDS))
    for _ in range(8):                       # a few tries in case peers claim rows under us
        row = conn.execute(
            "SELECT id, payload_json, attempts FROM interview_job WHERE status='queued' "
            "ORDER BY created_at LIMIT 1").fetchone()
        if not row:
            return None
        if row["attempts"] >= MAX_ATTEMPTS:
            # Keep the LAST REAL reason. Overwriting it with "max attempts" is what the candidate
            # then reads in their transcript — true, and useless. "gemini api HTTP 429: quota
            # exhausted; agy: not found" tells them (or the host) exactly what to do about it.
            conn.execute(
                "UPDATE interview_job SET status='failed', updated_at=?, "
                "error = CASE WHEN error IS NOT NULL AND error != '' "
                "             THEN error ELSE 'gave up after several attempts' END "
                "WHERE id=? AND status='queued'", (now, row["id"]))
            conn.commit()
            continue
        cur = conn.execute(
            "UPDATE interview_job SET status='leased', attempts=attempts+1, lease_until=?, "
            "updated_at=? WHERE id=? AND status='queued'", (until, now, row["id"]))
        conn.commit()
        if cur.rowcount == 1:                # we won the claim
            payload = json.loads(row["payload_json"])
            return {"job_id": row["id"], "prompt": payload.get("prompt", ""),
                    "system": payload.get("system", ""), "history": payload.get("history") or []}
    return None


def requeue(job_id: int, note: str = "") -> None:
    """Put a turn back WITHOUT spending one of its attempts.

    The attempt counter exists to stop an genuinely broken turn retrying forever. A rate limit is not
    that: nothing is wrong with the job, the quota is simply exhausted for a minute. Counting it
    meant three 429s killed a perfectly good turn — and on a free tier during real use, three is
    easy to reach. The turn now waits for the window to lift, or for a host machine running agy to
    pick it up, and the candidate's answer is never lost.
    """
    conn = db.connect()
    conn.execute(
        "UPDATE interview_job SET status='queued', lease_until=NULL, error=?, updated_at=?, "
        "attempts = CASE WHEN attempts > 0 THEN attempts - 1 ELSE 0 END WHERE id=?",
        (note[:400], _iso(), job_id))
    conn.commit()


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


def claim_for_apply(job_id: int) -> bool:
    """Atomically claim a finished job so its result is applied EXACTLY once.

    Applying a turn appends to the transcript and records rubric evidence, so doing it twice
    duplicates the interviewer's message and double-counts the answer. Overlapping polls make that
    easy to hit (a client polling every 2s has several requests in flight during a ~15s turn), and a
    refresh or a second tab would too. The single conditional UPDATE is the lock: only the request
    that actually flips done -> applying gets to run apply_turn.
    """
    conn = db.connect()
    cur = conn.execute(
        "UPDATE interview_job SET status='applying', updated_at=? WHERE id=? AND status='done'",
        (_iso(), job_id))
    conn.commit()
    return cur.rowcount == 1


def store_applied(job_id: int, applied: dict) -> None:
    conn = db.connect()
    conn.execute("UPDATE interview_job SET status='applied', result_json=?, updated_at=? WHERE id=?",
                 (json.dumps({"applied": applied}), _iso(), job_id))
    conn.commit()


def applied_result(job_id: int) -> dict | None:
    row = db.connect().execute(
        "SELECT status, result_json FROM interview_job WHERE id=?", (job_id,)).fetchone()
    if not row or row["status"] != "applied" or not row["result_json"]:
        return None
    try:
        return json.loads(row["result_json"]).get("applied")
    except Exception:
        return None


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
