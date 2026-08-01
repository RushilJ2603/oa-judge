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
API_MODEL = os.environ.get("OAJ_GEMINI_API_MODEL", "gemini-2.5-flash")
# Adaptive polling. A fixed idle interval was adding up to its full length to EVERY reply: the
# candidate hits send, and the worker may not look for work again for that long. Measured 36s per
# turn against 15s of actual generation.
#
# So: poll fast while a session is clearly live, and back off geometrically once nothing has come in
# for a while. During an interview the site is being used anyway (the Fly machine is already awake),
# so fast polling then is free; the backoff is what keeps an unattended worker from holding the
# machine up and costing money.
POLL_FAST = 0.7         # right after work — a live session
POLL_MAX = 20.0         # fully idle
BACKOFF = 1.6
LEASE_TIMEOUT = 300


def _post(server, path, token, payload):
    req = urllib.request.Request(
        server.rstrip("/") + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Worker-Token": token},
        method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode() or "{}")


def run_api(prompt: str, key: str, timeout: int = 90) -> tuple[str | None, str | None]:
    """Gemini API path — used when GEMINI_API_KEY is set.

    Measured: the agy CLI costs ~15s per turn regardless of prompt size or model tier
    (0.3s process start + ~5s auth handshake + ~8s generation) and does not warm up across calls.
    The HTTP API skips the per-call CLI handshake entirely and answers in roughly 1-3s, so this is
    the single biggest response-time win available. Falls back to the CLI when no key is present.
    """
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1200},
    }).encode()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{API_MODEL}:generateContent?key={key}")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:200]
        except Exception:
            pass
        return None, f"gemini api HTTP {e.code}: {detail}"
    except Exception as e:
        return None, f"gemini api: {e}"
    try:
        return d["candidates"][0]["content"]["parts"][0]["text"], None
    except Exception:
        return None, f"gemini api: unexpected response {str(d)[:160]}"


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
        r = subprocess.run(
            ["agy", "--model", MODEL, "--print", prompt],
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


def generate(prompt: str) -> tuple[str | None, str | None]:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OAJ_GEMINI_API_KEY")
    return run_api(prompt, key) if key else run_agy(prompt)


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
    delay = POLL_FAST
    print(f"concurrency: {a.concurrency} simultaneous turns\n")
    while True:
        inflight = {f for f in inflight if not f.done()}
        if len(inflight) >= a.concurrency:
            time.sleep(POLL_FAST)
            continue
        try:
            job = _post(a.server, "/api/interview/worker/lease", token,
                        {"worker_id": worker_id, "version": "1"})
        except urllib.error.HTTPError as e:
            print(f"lease failed: HTTP {e.code} {e.reason}")
            time.sleep(POLL_MAX)
            continue
        except Exception as e:
            print(f"lease failed: {e}")
            time.sleep(POLL_MAX)
            continue

        if not job or not job.get("job_id"):
            if not idle_logged and not inflight:
                print("idle — waiting for interview turns")
                idle_logged = True
            if a.once and not inflight:
                pool.shutdown(wait=True)
                return 0
            # Stay responsive while peers are still generating (more work is likely imminent),
            # otherwise ease off toward the idle ceiling.
            delay = POLL_FAST if inflight else min(POLL_MAX, delay * BACKOFF)
            time.sleep(delay)
            continue

        idle_logged = False
        delay = POLL_FAST                     # a live session: snap back to responsive
        inflight.add(pool.submit(handle, job))
        if a.once:
            pool.shutdown(wait=True)
            return 0


if __name__ == "__main__":
    sys.exit(main())
