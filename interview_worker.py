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

WRAPPER = os.path.expanduser(
    "~/.claude/plugins/marketplaces/antigravity-for-claude-code/scripts/agy-delegate.sh")
MODEL = os.environ.get("OAJ_INTERVIEW_MODEL", "gemini-3.6-flash-high")
POLL_IDLE = 20          # seconds between polls when no work; keeps Fly wake-ups infrequent
POLL_BUSY = 2
LEASE_TIMEOUT = 300


def _post(server, path, token, payload):
    req = urllib.request.Request(
        server.rstrip("/") + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Worker-Token": token},
        method="POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode() or "{}")


def run_agy(prompt: str, timeout: int = LEASE_TIMEOUT) -> tuple[str | None, str | None]:
    """Text in, text out. Empty scratch cwd + --sandbox + no workspace dirs."""
    scratch = tempfile.mkdtemp(prefix="oaj_iv_")
    try:
        r = subprocess.run(
            [WRAPPER, "-m", MODEL, "--sandbox", "--timeout", f"{timeout}s", "-"],
            input=prompt, capture_output=True, text=True, timeout=timeout + 30, cwd=scratch)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except FileNotFoundError:
        return None, f"agy wrapper not found at {WRAPPER}"
    finally:
        try:
            os.rmdir(scratch)
        except OSError:
            pass
    if r.returncode != 0:
        # exit 10 = quota, 11 = auth (see agy-delegate.sh) — surface these clearly, they need you.
        hint = {10: "QUOTA EXHAUSTED", 11: "AUTH — run `agy` once interactively"}.get(r.returncode, "")
        return None, f"agy exit {r.returncode} {hint}: {(r.stderr or '')[-200:]}"
    return r.stdout, None


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
    a = ap.parse_args()

    token = os.environ.get("OAJ_WORKER_TOKEN")
    if not token:
        sys.exit("OAJ_WORKER_TOKEN is not set — the worker must authenticate to lease jobs.")

    worker_id = f"{os.uname().nodename}-{os.getpid()}"
    print(f"interview worker {worker_id} -> {a.server}  (model {a.model})")
    print("This process is the host toggle: friends see 'Interviewer online' while it runs.\n")

    idle_logged = False
    while True:
        try:
            job = _post(a.server, "/api/interview/worker/lease", token,
                        {"worker_id": worker_id, "version": "1"})
        except urllib.error.HTTPError as e:
            print(f"lease failed: HTTP {e.code} {e.reason}")
            time.sleep(POLL_IDLE)
            continue
        except Exception as e:
            print(f"lease failed: {e}")
            time.sleep(POLL_IDLE)
            continue

        if not job or not job.get("job_id"):
            if not idle_logged:
                print("idle — waiting for interview turns")
                idle_logged = True
            if a.once:
                return 0
            time.sleep(POLL_IDLE)
            continue

        idle_logged = False
        jid = job["job_id"]
        print(f"job {jid}: generating turn…", end=" ", flush=True)
        t0 = time.time()
        out, err = run_agy(job.get("prompt", ""))
        dt = time.time() - t0

        if err or not looks_valid(out):
            reason = err or "model output did not match the required block"
            print(f"FAILED ({reason}) in {dt:.0f}s")
            _post(a.server, "/api/interview/worker/result", token,
                  {"worker_id": worker_id, "job_id": jid, "error": reason})
        else:
            print(f"ok in {dt:.0f}s")
            _post(a.server, "/api/interview/worker/result", token,
                  {"worker_id": worker_id, "job_id": jid, "output": out})

        if a.once:
            return 0
        time.sleep(POLL_BUSY)


if __name__ == "__main__":
    sys.exit(main())
