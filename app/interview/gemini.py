"""The Gemini HTTP client — ONE implementation, used by the server and by the local worker.

This lives in app/ rather than beside the worker because both callers need it and its parsing is
subtle enough that two copies would drift: a reasoning model returns several parts and the first may
be a thought, truncation must fail rather than deliver half an explanation, and a 429 carries the
retry window in its body. Each of those was a real bug found by testing rather than by reading.

Measured on a real interview turn (13.6 KB prompt), against agy's 16.1s for the same prompt:
    gemini-3.6-flash   5.4s   identical HIT/PARTIAL point ids and the same ADVANCE
"""
import json
import os
import re
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
# `gemini-2.5-flash` — the previous default — now returns 404 "no longer available to new users",
# which would have failed every turn. Verified present on a current key: gemini-3.6-flash.
MODEL = os.environ.get("OAJ_GEMINI_API_MODEL", "gemini-3.6-flash")
MAX_TOKENS = int(os.environ.get("OAJ_GEMINI_MAX_TOKENS", "3000"))
DEFAULT_COOLDOWN_S = float(os.environ.get("OAJ_API_COOLDOWN", "120"))
_RETRY_RE = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')


def key() -> str:
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("OAJ_GEMINI_API_KEY") or "").strip()


def available() -> bool:
    return bool(key())


def generate(prompt: str, timeout: int = 90, model: str = "") -> tuple[str | None, str | None, float]:
    """(text, error, retry_after_seconds). retry_after is > 0 only when we should stop asking."""
    k = key()
    if not k:
        return None, "no GEMINI_API_KEY", 0.0
    # maxOutputTokens must clear the LONGEST legitimate turn: the role contract asks for full
    # whiteboard-depth explanations when a candidate is stuck at the deepest hint tier, and a
    # truncated explanation is exactly the quality loss the fast path exists to avoid.
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": MAX_TOKENS},
    }).encode()
    # Key in a HEADER, never the query string — URLs reach proxy logs, access logs and error reports.
    req = urllib.request.Request(
        f"{API_ROOT}/models/{model or MODEL}:generateContent", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-goog-api-key": k})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:400]
        except Exception:
            pass
        # Honour Google's own RetryInfo over a guess: it knows when the window resets.
        m = _RETRY_RE.search(detail)
        wait = float(m.group(1)) if m else (DEFAULT_COOLDOWN_S if e.code in (429, 503) else 0.0)
        return None, f"gemini api HTTP {e.code}: {detail[:200]}", wait
    except Exception as e:
        return None, f"gemini api: {e}", 0.0

    try:
        cand = (d.get("candidates") or [])[0]
    except IndexError:
        fb = (d.get("promptFeedback") or {}).get("blockReason")
        return None, f"gemini api: no candidates{f' (blocked: {fb})' if fb else ''}", 0.0
    # Join EVERY non-thought text part. Taking parts[0] hands back the model's reasoning instead of
    # its answer, which does not fail loudly — it parses to an empty block and reads downstream as
    # "the interviewer said nothing".
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p["text"] for p in parts
                   if isinstance(p, dict) and "text" in p and not p.get("thought"))
    reason = cand.get("finishReason")
    if not text:
        return None, f"gemini api: empty reply (finishReason={reason})", 0.0
    # ALLOWLIST, not a blocklist. Only STOP means the model finished saying what it meant to say.
    # SAFETY, RECITATION, BLOCKLIST, PROHIBITED_CONTENT and SPII all cut generation off mid-reply
    # while LEAVING the text produced so far in place — so blocklisting MAX_TOKENS alone let a
    # half-written turn through as if it were complete. The student would see an explanation that
    # stops mid-sentence, and the grading block attached to it would be applied as final.
    # (A missing finishReason is treated as fine: it means the field was simply not sent.)
    if reason not in (None, "", "STOP"):
        hint = (" — raise OAJ_GEMINI_MAX_TOKENS" if reason == "MAX_TOKENS" else "")
        return None, f"gemini api: reply cut short (finishReason={reason}){hint}", 0.0
    return text, None, 0.0
