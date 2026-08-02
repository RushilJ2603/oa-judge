#!/usr/bin/env python3
"""Which path answers a turn, and what happens when the fast one refuses.

This is load-bearing rather than cosmetic. The free-tier API key rate-limits after very few requests
in quick succession (measured: three back-to-back calls, third returns 429), so a live interview WILL
hit it. If a 429 surfaced as an error the candidate would watch their interview die mid-answer; it
has to route to agy instead, silently and immediately.

No network and no agy spawn — both paths are stubbed, because what is under test is the ROUTING.

Run:  python3 test_worker_routing.py     (exits non-zero on failure)
"""
import importlib.util
import io
import json
import os
import sys
import time
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
FAILS = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"   {detail}" if not cond and detail else ""))
    if not cond:
        FAILS.append(name)


def load(**env):
    """A fresh import per case: the path choice is read at import time."""
    for k in ("OAJ_INTERVIEW_PATH", "GEMINI_API_KEY", "OAJ_GEMINI_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update(env)
    spec = importlib.util.spec_from_file_location("w", os.path.join(HERE, "interview_worker.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def stub(m, api_result, calls):
    # **kwargs so the stub keeps working as the real signatures grow (system/history were added when
    # the API path started sending a real conversation instead of a flat blob).
    m.run_api = lambda p, k, **kw: (calls.append("api"), api_result)[1]
    m.run_agy = lambda p, **kw: (calls.append("agy"), ("AGY-REPLY", None))[1]


def main():
    print("worker routing\n")
    cases = [
        ("auto + key, api answers", dict(GEMINI_API_KEY="k"), ("API-REPLY", None, 0.0),
         "API-REPLY", ["api"]),
        ("auto + key, api 429 -> agy", dict(GEMINI_API_KEY="k"), (None, "HTTP 429", 7.0),
         "AGY-REPLY", ["api", "agy"]),
        ("auto + key, api broken -> agy", dict(GEMINI_API_KEY="k"), (None, "HTTP 500", 0.0),
         "AGY-REPLY", ["api", "agy"]),
        ("auto, no key -> agy only", dict(), None, "AGY-REPLY", ["agy"]),
        ("path=agy ignores the key", dict(GEMINI_API_KEY="k", OAJ_INTERVIEW_PATH="agy"),
         ("API-REPLY", None, 0.0), "AGY-REPLY", ["agy"]),
        ("path=api uses the api", dict(GEMINI_API_KEY="k", OAJ_INTERVIEW_PATH="api"),
         ("API-REPLY", None, 0.0), "API-REPLY", ["api"]),
    ]
    for name, env, api_result, want, want_calls in cases:
        m = load(**env)
        calls = []
        stub(m, api_result, calls)
        out, _err = m.generate("p")
        check(name, out == want and calls == want_calls, f"got {out!r} calls={calls}")

    # A misconfiguration must be loud, not silently slow.
    m = load(OAJ_INTERVIEW_PATH="api")
    stub(m, None, [])
    out, err = m.generate("p")
    check("path=api without a key fails loudly", out is None and "no GEMINI_API_KEY" in (err or ""),
          f"err={err!r}")

    # Retrying a rate-limited key every turn wastes a round trip and digs the hole deeper.
    m = load(GEMINI_API_KEY="k")
    calls = []
    stub(m, (None, "HTTP 429", 5.0), calls)
    m.generate("p")
    calls.clear()
    m.generate("p")
    check("while cooling down, the api is not retried", calls == ["agy"], str(calls))
    m._api_blocked_until = time.monotonic() - 1
    calls.clear()
    stub(m, ("API-REPLY", None, 0.0), calls)
    m.generate("p")
    check("after the window, the fast path resumes", calls == ["api"], str(calls))

    # Google tells us when the window resets; guessing is strictly worse.
    m = load(GEMINI_API_KEY="k")
    body = json.dumps({"error": {"code": 429, "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "27s"}]}}).encode()

    def raise429(*a, **k):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(body))

    m.urllib.request.urlopen = raise429
    _out, _err, wait = m.run_api("p", "k")
    check("cooldown honours the API's own retryDelay", wait == 27.0, f"got {wait}")

    # The model that used to be the default is gone; a stale id fails every turn.
    m = load()
    check("api model default is not the retired gemini-2.5-flash",
          m.API_MODEL != "gemini-2.5-flash", m.API_MODEL)

    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}): {', '.join(FAILS)}")
        return 1
    print("ALL WORKER ROUTING CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
