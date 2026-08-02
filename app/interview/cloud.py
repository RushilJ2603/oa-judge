"""Answer interview turns on the SERVER, so the interviewer works with no laptop running.

The local agy worker was the only thing that could answer a turn, which meant the interviewer was
online exactly when the host's machine was. Calling Gemini is just an HTTPS request, so the server
can do it itself — and then the site is always available to the host and their friends.

Deliberately a background thread over the SAME job queue rather than answering inline in the request:

  * the queue stays the single source of truth, so an agy worker and this can both take work and
    whoever leases a row first runs it (`lease` is one conditional UPDATE — see jobs.py);
  * the apply-once machinery, hint gating and scoring are untouched, because nothing about how a
    turn is applied changes — only who produced the text;
  * a web request is never held for the ~5s a model call takes, so a room of people answering at
    once cannot exhaust the server's threads.

Rate limits are the reason the local worker still matters. The free tier 429s after very few rapid
calls, so on a 429 this backs off for exactly as long as Google says and leaves the queue alone —
an agy worker, if the host has one running, picks those turns up instead. If nobody does, the turns
wait and are retried, which is the correct outcome: slower, never wrong.

Scale-to-zero is safe: jobs only exist while someone is interviewing, which means the machine is
already awake serving them.
"""
import os
import threading
import time

from . import gemini, jobs

WORKER_ID = "cloud"
POLL_IDLE_S = float(os.environ.get("OAJ_CLOUD_POLL", "0.5"))
CONCURRENCY = int(os.environ.get("OAJ_CLOUD_CONCURRENCY", "4"))

_started = False
_lock = threading.Lock()
_blocked_until = 0.0            # set on a 429; the queue is left to agy workers meanwhile
_stats = {"done": 0, "failed": 0, "rate_limited": 0}


def healthy() -> bool:
    """Can the server answer a turn right now? Drives the 'cloud' half of the status dot."""
    return gemini.available() and time.monotonic() >= _blocked_until


def stats() -> dict:
    return dict(_stats, blocked_for=max(0.0, _blocked_until - time.monotonic()))


def _looks_valid(text: str) -> bool:
    """Same acceptance test the local worker applies: never hand the server something that is not
    the expected block, or a malformed reply becomes a silent empty turn."""
    up = (text or "").upper()
    return "SAY:" in up and ("HIT:" in up or "ADVANCE:" in up)


def _run_one(job: dict) -> None:
    global _blocked_until
    out, err, retry_after = gemini.generate(job.get("prompt", ""))
    if retry_after:
        with _lock:
            _blocked_until = max(_blocked_until, time.monotonic() + retry_after)
        _stats["rate_limited"] += 1
        # Put it straight back rather than burning an attempt on a limit that is not the job's fault.
        jobs.complete(job["job_id"], error=err or "rate limited")
        return
    if err or not _looks_valid(out):
        _stats["failed"] += 1
        jobs.complete(job["job_id"], error=err or "model output did not match the required block")
        return
    _stats["done"] += 1
    jobs.complete(job["job_id"], output=out)


def _loop(app) -> None:
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=CONCURRENCY, thread_name_prefix="cloud-iv")
    inflight: set = set()
    while True:
        try:
            inflight = {f for f in inflight if not f.done()}
            if len(inflight) >= CONCURRENCY or not healthy():
                time.sleep(POLL_IDLE_S)
                continue
            with app.app_context():
                # No heartbeat: worker_beat means "a HOST machine is up", and writing to it here
                # would make the UI claim agy is available when only the API is.
                job = jobs.lease(WORKER_ID, "cloud", heartbeat=False)
            if not job:
                time.sleep(POLL_IDLE_S)
                continue

            def work(j=job):
                with app.app_context():
                    try:
                        _run_one(j)
                    except Exception as e:                      # never kill the pool thread
                        try:
                            jobs.complete(j["job_id"], error=f"cloud worker: {e}")
                        except Exception:
                            pass

            inflight.add(pool.submit(work))
        except Exception:
            # A transient DB or network error must not end the loop; the machine may run for weeks.
            time.sleep(2.0)


def start(app) -> bool:
    """Start the background answerer once, if a key is configured. Returns whether it is running."""
    global _started
    with _lock:
        if _started or not gemini.available():
            return _started
        t = threading.Thread(target=_loop, args=(app,), name="cloud-interviewer", daemon=True)
        t.start()
        _started = True
        return True
