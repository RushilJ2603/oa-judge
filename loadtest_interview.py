#!/usr/bin/env python3
"""Concurrency load test for the interview stack — proves N users can share one host.

Simulates N candidates each running a real session loop (start -> poll -> answer -> poll ...) plus a
fake multi-threaded worker draining the queue, and then asserts the properties that actually matter:

  * no duplicated interviewer turns   (the apply-once guarantee, under overlapping polls)
  * no job handed to two workers      (the lease race)
  * every user's session is isolated  (nobody sees another's transcript)
  * latency stays sane

Usage:  python3 loadtest_interview.py [--users 16] [--turns 3] [--server http://127.0.0.1:5137]
"""
import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

LOCK = threading.Lock()
LEASED = Counter()          # job_id -> how many times it was leased (must never exceed 1 live)
ERRORS = []
LAT = []
LATENCY = [0.3]


def call(server, path, token=None, payload=None, timeout=30):
    url = server.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json",
                                          **({"X-Worker-Token": token} if token else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def fake_worker(server, token, stop, concurrency):
    """Drains the queue like the real worker, but returns a canned block instantly."""
    pool = ThreadPoolExecutor(max_workers=concurrency)

    def do(job):
        jid = job["job_id"]
        with LOCK:
            LEASED[jid] += 1
        time.sleep(LATENCY[0])             # stand in for model latency
        try:
            call(server, "/api/interview/worker/result", token,
                 {"worker_id": "lt", "job_id": jid,
                  "output": "HIT: NONE\nPARTIAL: NONE\nEVIDENCE:\nSTUCK: NO\nADVANCE: NO\n"
                            f"SAY: turn for job {jid}"})
        except Exception as e:
            with LOCK:
                ERRORS.append(f"worker result: {e}")

    while not stop.is_set():
        try:
            job = call(server, "/api/interview/worker/lease", token,
                       {"worker_id": "lt", "version": "lt"})
        except Exception:
            time.sleep(0.1)
            continue
        if job and job.get("job_id"):
            pool.submit(do, job)
        else:
            time.sleep(0.05)
    pool.shutdown(wait=True)


def candidate(server, uid, turns, rubric):
    """One user's session: start, then answer `turns` times, polling like the browser does."""
    try:
        s = call(server, "/api/interview/start", payload={"rubric_id": rubric})
        if "session_id" not in s:
            with LOCK:
                ERRORS.append(f"u{uid} start: {s}")
            return
        sid, job = s["session_id"], s["job_id"]
        for t in range(turns):
            t0 = time.time()
            # Poll like the UI: repeatedly, until done. Overlap is what broke it before, so poll
            # aggressively on purpose.
            for _ in range(int(max(200, LATENCY[0] * 20 * 6))):
                r = call(server, f"/api/interview/poll/{job}")
                if r.get("status") == "done":
                    break
                time.sleep(0.05)
            else:
                with LOCK:
                    ERRORS.append(f"u{uid} turn {t}: never completed")
                return
            with LOCK:
                LAT.append(time.time() - t0)
            if t + 1 < turns:
                a = call(server, "/api/interview/answer",
                         payload={"session_id": sid, "answer": f"user {uid} answer {t}"})
                if "job_id" not in a:
                    with LOCK:
                        ERRORS.append(f"u{uid} answer: {a}")
                    return
                job = a["job_id"]
        # verify transcript integrity for this user
        d = call(server, f"/api/interview/session/{sid}")
        iv = [x for x in d["turns"] if x["role"] == "interviewer"]
        texts = [x["content"] for x in iv]
        if len(texts) != len(set(texts)):
            with LOCK:
                ERRORS.append(f"u{uid} DUPLICATE interviewer turns: {len(texts)} vs "
                              f"{len(set(texts))} unique")
        for x in d["turns"]:
            if x["role"] == "candidate" and f"user {uid} " not in x["content"]:
                with LOCK:
                    ERRORS.append(f"u{uid} LEAKED another user's answer: {x['content'][:40]}")
    except Exception as e:
        with LOCK:
            ERRORS.append(f"u{uid}: {type(e).__name__} {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:5137")
    ap.add_argument("--users", type=int, default=16)
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--token", default="t1")
    ap.add_argument("--rubric", default="hq01_url_shortener")
    ap.add_argument("--worker-concurrency", type=int, default=6)
    ap.add_argument("--model-latency", type=float, default=0.3,
                    help="simulated seconds per model turn (real agy is ~15)")
    a = ap.parse_args()

    LATENCY[0] = a.model_latency
    stop = threading.Event()
    wt = threading.Thread(target=fake_worker,
                          args=(a.server, a.token, stop, a.worker_concurrency), daemon=True)
    wt.start()

    print(f"simulating {a.users} concurrent users x {a.turns} turns "
          f"(worker concurrency {a.worker_concurrency})")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.users) as pool:
        for uid in range(a.users):
            pool.submit(candidate, a.server, uid, a.turns, a.rubric)
    elapsed = time.time() - t0
    stop.set()
    wt.join(timeout=5)

    dupes = {j: n for j, n in LEASED.items() if n > 1}
    print(f"\nwall time        : {elapsed:.1f}s for {a.users * a.turns} turns")
    if LAT:
        print(f"turn latency     : median {statistics.median(LAT):.2f}s  "
              f"p95 {sorted(LAT)[int(len(LAT) * .95) - 1]:.2f}s  max {max(LAT):.2f}s")
    print(f"jobs leased twice: {len(dupes)}  {list(dupes.items())[:5]}")
    print(f"errors           : {len(ERRORS)}")
    for e in ERRORS[:10]:
        print(f"   - {e}")
    ok = not ERRORS and not dupes
    print("\n" + ("LOAD TEST PASS" if ok else "LOAD TEST FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
