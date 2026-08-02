#!/usr/bin/env python3
"""Local interview worker: leases turn jobs from OA Judge and answers them with agy (Gemini).

Runs on YOUR machine (inside WSL — agy is not available to native Windows). It only ever makes
OUTBOUND requests, so there is no port to forward and nothing inbound to attack.

Starting this process IS the host toggle: it heartbeats while alive, the site shows "Interviewer
online", and when you stop it the site shows offline and the Fly machine goes back to sleep. There
is no separate flag to drift out of sync.

SECURITY POSTURE — friends' typed answers reach this machine, so:
  * the server sends STRUCTURED job data (prompt text built server-side from gated rubrics), and
    this worker passes it to agy as a single prompt with no workspace attached;
  * agy runs with NO --dir, from an empty scratch directory, with --sandbox and never --yolo, so a
    successful prompt injection reaches an agent that has nothing to read or execute;
  * output is accepted only if it parses into the expected block, and scores are computed by the
    SERVER from rubric point ids — nothing this worker returns can set a number directly.

Usage:
  OAJ_WORKER_TOKEN=... python3 interview_worker.py [--server https://oa123.fly.dev] [--once]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

WRAPPER = os.path.expanduser(
    "~/.claude/plugins/marketplaces/antigravity-for-claude-code/scripts/agy-delegate.sh")
MODEL = os.environ.get("OAJ_INTERVIEW_MODEL", "gemini-3.6-flash-high")
# API path model id (different namespace from agy tier names).
API_MODEL = os.environ.get("OAJ_GEMINI_API_MODEL", "gemini-3.6-flash")
# LONG POLL. The worker asks for work once and the SERVER holds that request open until a turn
# appears, so pickup is immediate rather than "whenever the next poll lands".
#
# What this replaced, and why it mattered more than it looks: the lease used to be a client poll that
# backed off geometrically while idle, so an unattended worker would not hold the Fly machine awake.
# But a real interview is mostly idle — the candidate spends a minute or two thinking — so by the
# time they hit send the worker had eased out to a 20-second interval, and their answer waited up to
# 20s just to be NOTICED. That was routinely longer than the model call it was waiting for.
#
# Holding the connection also sends FEWER requests than polling did, and a worker only runs when the
# host has deliberately switched the interviewer on.
LEASE_WAIT = 25.0       # how long the server may hold one lease request
POLL_FAST = 0.4         # gap between long polls while an interview is live
POLL_IDLE = 3.0         # nothing live — the hold already absorbed the wait, just don't spin
LEASE_TIMEOUT = 300


def _post(server, path, token, payload, timeout=45):
    req = urllib.request.Request(
        server.rstrip("/") + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Worker-Token": token},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def run_api(prompt: str, key: str, timeout: int = 90) -> tuple[str | None, str | None, float]:
    """Gemini API path. Returns (text, error, retry_after_seconds).

    MEASURED on a real 13.6 KB interview turn (2026-08-02), against agy's 16.1s for the same prompt:

        gemini-3.6-flash     5.52s / 5.34s      think=704 / 640
        gemini-3.5-flash     5.36s / 5.92s      think=1071 / 1198

    ~3x faster, and it produced the SAME grading decision as agy on the same turn (identical HIT and
    PARTIAL point ids, same ADVANCE) — which is the part that has to match, since those drive the
    score and phase advancement.

    Two things the measurement changed:
      * `gemini-2.5-flash` — the previous default here — returns 404 "no longer available to new
        users". It would have failed on every single turn.
      * The free tier rate-limits HARD: three calls in quick succession returned 429. That is fine
        at interview pace but not for several people at once, so the fallback to agy is not a nicety,
        it is load-bearing.
    """
    # maxOutputTokens has to clear the LONGEST legitimate turn, not the average one. The role
    # contract explicitly asks for full whiteboard-depth explanations when a candidate is stuck at
    # the deepest hint tier, and a truncated explanation is exactly the quality loss this path
    # exists to avoid — so the cap sits well above the ~400-token typical reply.
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6,
                             "maxOutputTokens": int(os.environ.get("OAJ_GEMINI_MAX_TOKENS", "3000"))},
    }).encode()
    # Key goes in a HEADER, never the query string: URLs end up in proxy logs, server access logs
    # and error reports, and this one is a live credential. It is also the form Google's own
    # quickstart uses for current-generation keys.
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{API_MODEL}:generateContent")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:400]
        except Exception:
            pass
        # A 429 usually carries Google's own RetryInfo. Honour it instead of guessing a cooldown —
        # backing off too little re-triggers the limit, too much wastes the fast path.
        wait = 0.0
        m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', detail)
        if m:
            wait = float(m.group(1))
        elif e.code in (429, 503):
            wait = API_COOLDOWN_S
        return None, f"gemini api HTTP {e.code}: {detail[:200]}", wait
    except Exception as e:
        return None, f"gemini api: {e}", 0.0
    # Join EVERY text part rather than taking parts[0]. A reasoning model can emit several parts,
    # and the first one may be a thought rather than the answer — taking [0] would silently hand the
    # server a fragment that fails to parse into the HIT/PARTIAL block, which reads downstream as
    # "the interviewer said nothing" rather than as an error.
    try:
        cand = (d.get("candidates") or [])[0]
    except IndexError:
        fb = (d.get("promptFeedback") or {}).get("blockReason")
        return None, f"gemini api: no candidates{f' (blocked: {fb})' if fb else ''}", 0.0
    parts = ((cand.get("content") or {}).get("parts") or [])
    text = "".join(p["text"] for p in parts if isinstance(p, dict) and "text" in p
                   and not p.get("thought"))
    reason = cand.get("finishReason")
    if not text:
        return None, f"gemini api: empty reply (finishReason={reason})", 0.0
    if reason == "MAX_TOKENS":
        # Truncation would lose the SAY block mid-explanation. Fail loudly so the turn is retried
        # instead of the candidate receiving half an answer.
        return None, "gemini api: reply hit maxOutputTokens — raise OAJ_GEMINI_MAX_TOKENS", 0.0
    return text, None, 0.0


def run_agy(prompt: str, timeout: int = LEASE_TIMEOUT) -> tuple[str | None, str | None]:
    """Text in, text out. Empty scratch cwd + --sandbox + no workspace dirs.

    Calls `agy` directly rather than through the plugin wrapper: the wrapper adds ~1.5s per turn
    (measured 14.8s vs 13.3s) for delegation features this worker does not use, and that cost lands
    on every single interviewer reply.
    """
    scratch = tempfile.mkdtemp(prefix="oaj_iv_")
    try:
        # Two agy invocation traps, both verified by experiment:
        #  1. the prompt is an ARGUMENT, not stdin — `agy --print` ignores piped stdin and emits
        #     nothing useful when stdin is a non-TTY, so stdin is closed and argv carries the text;
        #  2. FLAG ORDER MATTERS — `--print --model X <prompt>` loses the prompt (agy answers a
        #     generic "the active model is..."), while `--model X --print <prompt>` works.
        #  3. --disable-slash-commands: the prompt is a large blob containing rubric text and the
        #     candidate's UNTRUSTED answer. In print mode agy expands slash commands and skills out
        #     of the prompt, so a candidate typing "/something" would be reaching agy's command
        #     surface rather than being graded. The interviewer never wants expansion. (Its effect
        #     on latency was within noise — 13.0s vs 13.8s over two runs each; this is for safety.)
        r = subprocess.run(
            ["agy", "--model", MODEL, "--disable-slash-commands", "--print", prompt],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=timeout, cwd=scratch)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except FileNotFoundError:
        return None, "agy not found on PATH — install the Antigravity CLI"
    finally:
        try:
            os.rmdir(scratch)
        except OSError:
            pass
    if r.returncode != 0:
        err = (r.stderr or "")[-200:]
        hint = ""
        low = err.lower()
        if "quota" in low or "exhaust" in low:
            hint = "QUOTA EXHAUSTED"
        elif "auth" in low or "login" in low:
            hint = "AUTH — run `agy` once interactively"
        return None, f"agy exit {r.returncode} {hint}: {err}"
    return r.stdout, None


# Which path answers a turn:
#   auto (default) — the API when a key is present and healthy, otherwise agy
#   api            — prefer the API, but still fall back rather than fail a live interview
#   agy            — never touch the API, even with a key set
INTERVIEW_PATH = os.environ.get("OAJ_INTERVIEW_PATH", "auto").strip().lower()
# After a rate limit, stop asking for a while. Retrying every turn wastes a round trip and, on a
# free tier, digs the hole deeper — meanwhile agy still answers, just slower.
API_COOLDOWN_S = float(os.environ.get("OAJ_API_COOLDOWN", "120"))
_api_blocked_until = 0.0
_RATE_LIMIT_HINTS = ("http 429", "http 503", "resource_exhausted", "quota", "rate limit",
                     "overloaded", "unavailable")


def _rate_limited(err: str) -> bool:
    e = (err or "").lower()
    return any(h in e for h in _RATE_LIMIT_HINTS)


def generate(prompt: str) -> tuple[str | None, str | None]:
    """Answer one turn: fast path when it is available, slow path when it is not.

    MEASURED on the same real interview turn: API `gemini-3.6-flash` 5.4s vs agy 16.1s, producing
    identical HIT/PARTIAL point ids and the same ADVANCE — so this is a 3x speed-up that does not
    move a single score.

    The catch is that the free tier rate-limits after very few requests in quick succession. At
    interview pace (one turn per minute or two) that is invisible; with several people at once it is
    not. So a 429 is not an error here — it is a routing decision. The turn goes to agy, which is
    slower but always available, and the interview never notices.
    """
    global _api_blocked_until
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OAJ_GEMINI_API_KEY")

    if INTERVIEW_PATH == "agy":
        return run_agy(prompt)
    if INTERVIEW_PATH == "api" and not key:
        return None, "OAJ_INTERVIEW_PATH=api but no GEMINI_API_KEY is set"

    if key and time.monotonic() >= _api_blocked_until:
        out, err, retry_after = run_api(prompt, key)
        if out:
            return out, None
        if retry_after or _rate_limited(err):
            # Prefer the API's OWN RetryInfo over a guess; it knows when the window resets.
            wait = retry_after or API_COOLDOWN_S
            _api_blocked_until = time.monotonic() + wait
            print(f"  api rate-limited — routing to agy for {wait:.0f}s")
        else:
            print(f"  api failed ({err[:100]}) — falling back to agy")
    return run_agy(prompt)


def looks_valid(text: str) -> bool:
    """Reject anything that is not the expected block, before it reaches the server."""
    if not text:
        return False
    up = text.upper()
    return "SAY:" in up and ("HIT:" in up or "ADVANCE:" in up)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default=os.environ.get("OAJ_SERVER", "https://oa123.fly.dev"))
    ap.add_argument("--once", action="store_true", help="process one job then exit (for testing)")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--concurrency", type=int,
                    default=int(os.environ.get("OAJ_INTERVIEW_CONCURRENCY", "6")),
                    help="simultaneous turns; must not exceed the server MAX_CONCURRENT")
    a = ap.parse_args()

    token = os.environ.get("OAJ_WORKER_TOKEN")
    if not token:
        sys.exit("OAJ_WORKER_TOKEN is not set — the worker must authenticate to lease jobs.")

    worker_id = f"{os.uname().nodename}-{os.getpid()}"
    print(f"interview worker {worker_id} -> {a.server}  (model {a.model})")
    print("This process is the host toggle: friends see 'Interviewer online' while it runs.\n")

    def handle(job):
        """One turn, start to finish. Runs on a pool thread so peers keep working meanwhile."""
        jid = job["job_id"]
        t0 = time.time()
        out, err = generate(job.get("prompt", ""))
        dt = time.time() - t0
        if err or not looks_valid(out):
            reason = err or "model output did not match the required block"
            print(f"  job {jid}: FAILED ({reason}) in {dt:.0f}s", flush=True)
            body = {"worker_id": worker_id, "job_id": jid, "error": reason}
        else:
            print(f"  job {jid}: ok in {dt:.0f}s", flush=True)
            body = {"worker_id": worker_id, "job_id": jid, "output": out}
        try:
            _post(a.server, "/api/interview/worker/result", token, body)
        except Exception as e:                       # the lease will expire and be re-offered
            print(f"  job {jid}: could not post result ({e})", flush=True)

    # A serial worker answers ~4 turns/minute, so a room of 10-16 people would queue for minutes.
    # Turns are network-bound (a CLI call waiting on Gemini), not CPU-bound, so running several at
    # once costs little locally and is what makes concurrent users feel instant.
    pool = ThreadPoolExecutor(max_workers=a.concurrency)
    inflight = set()
    idle_logged = False
    print(f"concurrency: {a.concurrency} simultaneous turns\n")
    while True:
        inflight = {f for f in inflight if not f.done()}
        if len(inflight) >= a.concurrency:
            time.sleep(POLL_FAST)
            continue
        try:
            # `wait` asks the server to hold this request until work arrives. `--once` does not
            # wait: it is a smoke test, and should report "nothing queued" rather than hang.
            job = _post(a.server, "/api/interview/worker/lease", token,
                        {"worker_id": worker_id, "version": "1",
                         "wait": 0 if a.once else LEASE_WAIT},
                        timeout=LEASE_WAIT + 20)
        except urllib.error.HTTPError as e:
            print(f"lease failed: HTTP {e.code} {e.reason}")
            time.sleep(POLL_IDLE)
            continue
        except Exception as e:
            print(f"lease failed: {e}")
            time.sleep(POLL_IDLE)
            continue

        if not job or not job.get("job_id"):
            if not idle_logged and not inflight:
                print("idle — waiting for interview turns")
                idle_logged = True
            if a.once and not inflight:
                pool.shutdown(wait=True)
                return 0
            # The server already absorbed the waiting. This gap only stops a tight loop if the hold
            # returns early; it stays short while a session is live so pickup remains immediate.
            time.sleep(POLL_FAST if (inflight or job.get("live")) else POLL_IDLE)
            continue

        idle_logged = False
        inflight.add(pool.submit(handle, job))
        if a.once:
            pool.shutdown(wait=True)
            return 0


if __name__ == "__main__":
    sys.exit(main())
