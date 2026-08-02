#!/usr/bin/env python3
"""Decide the agy-vs-API question with evidence instead of a guess.

The API path answers a turn in ~5s where the agy CLI takes ~16.5s, because agy re-authenticates and
rebuilds a session on every single turn (measured: ~10.5s of bootstrap before the model is called).
That is a big win — but ONLY if quality is unchanged, and quality equivalence cannot be assumed here:

  * `gemini-3.6-flash-high` is an ANTIGRAVITY TIER LABEL, not a public model id. agy's own log shows
    it being resolved by Google's Code Assist backend ("Propagating selected model override to
    backend: label=\"Gemini 3.6 Flash (High)\""), which is a different product surface from the AI
    Studio API. There is no model of that name to request over HTTP.
  * "(High)" is an effort tier. On the CLI it produced 1888 thinking tokens on a real interview turn.
    Over the API, thinking is a request parameter, so it has to be asked for explicitly.

So this script runs the SAME real interview prompt down both paths and shows what actually differs.
The comparison that matters is not whether the prose reads nicely — it is whether the two paths make
the SAME GRADING DECISIONS, because those drive scores, hint release and phase advancement.

Usage:
    python3 compare_interview_paths.py --list                  # what does the key actually offer?
    python3 compare_interview_paths.py --models gemini-2.5-flash,gemini-2.5-pro
    python3 compare_interview_paths.py --rubric hq01_url_shortener --repeat 2

Needs GEMINI_API_KEY in the environment (or .env, which the launcher already sources).
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "app"))

AGY_MODEL = os.environ.get("OAJ_INTERVIEW_MODEL", "gemini-3.6-flash-high")
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("OAJ_GEMINI_API_KEY")
    if k:
        return k
    env = os.path.join(HERE, ".env")           # same file the launcher sources
    if os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            if line.strip().startswith(("GEMINI_API_KEY=", "OAJ_GEMINI_API_KEY=")):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def list_models(key: str) -> list[dict]:
    """What the key can actually reach. This is the only authoritative answer to 'is the same model
    available?' — everything else is inference."""
    req = urllib.request.Request(f"{API_ROOT}/models?pageSize=200",
                                 headers={"X-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    out = []
    for m in d.get("models", []):
        if "generateContent" in (m.get("supportedGenerationMethods") or []):
            out.append({"id": m["name"].split("/", 1)[-1],
                        "display": m.get("displayName", ""),
                        "in": m.get("inputTokenLimit", 0),
                        "out": m.get("outputTokenLimit", 0)})
    return out


def build_prompt(rubric_id: str) -> str:
    """A REAL turn from the live corpus — same assembly the server does, so the comparison is on the
    actual workload rather than a toy prompt."""
    import db
    from interview import session as iv
    db.connect()
    db.init()
    uid = 99001
    s = iv.start(uid, rubric_id)
    if not s:
        raise SystemExit(f"unknown rubric {rubric_id!r}")
    sid = s["session_id"]
    iv.add_turn(sid, uid, "interviewer", "Let's start with the requirements.", s["phase"])
    iv.add_turn(sid, uid, "candidate",
                "We take a long URL and return a short one, and redirect on lookup. Reads dominate "
                "writes heavily, maybe 100 to 1. The redirect path needs low latency. I'd want the "
                "short code to be short enough to type but large enough not to collide.", s["phase"])
    return iv.build_prompt(uid, sid)


def run_agy(prompt: str) -> tuple[str, float]:
    t0 = time.monotonic()
    r = subprocess.run(["agy", "--model", AGY_MODEL, "--disable-slash-commands", "--print", prompt],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd="/tmp",
                       timeout=300)
    return (r.stdout or r.stderr or "").strip(), time.monotonic() - t0


LAST_USAGE: dict = {}


def run_api(prompt: str, key: str, model: str, thinking: int | None) -> tuple[str, float]:
    gen = {"temperature": 0.6, "maxOutputTokens": 3000}
    if thinking is not None:
        # The CLI's "(High)" tier spent 1888 thinking tokens on this workload. Over HTTP that has to
        # be requested, or the API path would be quietly doing less reasoning than the CLI — the
        # exact silent quality regression this whole comparison exists to catch.
        gen["thinkingConfig"] = {"thinkingBudget": thinking}
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": gen}).encode()
    req = urllib.request.Request(f"{API_ROOT}/models/{model}:generateContent",
                                 data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-goog-api-key": key})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return f"__ERROR__ HTTP {e.code}: {e.read().decode()[:180]}", time.monotonic() - t0
    except Exception as e:
        return f"__ERROR__ {e}", time.monotonic() - t0
    took = time.monotonic() - t0
    # Reasoning effort is the crux of the comparison: agy's "(High)" tier spent 1456-1888 thinking
    # tokens on this workload, so an API call that thinks far less is doing a different job.
    u = d.get("usageMetadata") or {}
    LAST_USAGE.clear()
    LAST_USAGE.update({"think": u.get("thoughtsTokenCount", 0),
                       "out": u.get("candidatesTokenCount", 0),
                       "in": u.get("promptTokenCount", 0)})
    cands = d.get("candidates") or []
    if not cands:
        return f"__ERROR__ no candidates: {str(d)[:180]}", took
    parts = ((cands[0].get("content") or {}).get("parts") or [])
    text = "".join(p["text"] for p in parts
                   if isinstance(p, dict) and "text" in p and not p.get("thought"))
    if cands[0].get("finishReason") == "MAX_TOKENS":
        return "__ERROR__ truncated at maxOutputTokens", took
    return text.strip(), took


def summarise(label: str, raw: str, took: float) -> dict:
    """Reduce a reply to the things the APP acts on. Prose differences are expected and fine; a
    different HIT set is a different score, and a different ADVANCE is a different interview."""
    from interview import context
    if raw.startswith("__ERROR__"):
        return {"label": label, "took": took, "error": raw[10:]}
    p = context.parse_response(raw)
    return {"label": label, "took": took, "hit": sorted(p["hit"]), "partial": sorted(p["partial"]),
            "advance": p["advance"], "stuck": p["stuck"], "say": p["say"],
            "say_len": len(p["say"]), "parsed": bool(p["say"])}


def show(r: dict) -> None:
    if r.get("error"):
        print(f"  {r['label']:34} {r['took']:6.2f}s  ERROR: {r['error']}")
        return
    u = r.get("usage") or {}
    think = f" think={u['think']}" if u.get("think") is not None and u else ""
    print(f"  {r['label']:30} {r['took']:6.2f}s  hit={r['hit'] or '-'} partial={r['partial'] or '-'} "
          f"advance={r['advance']} say={r['say_len']}ch{think}"
          f"{'' if r['parsed'] else '  <-- DID NOT PARSE'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="list models the key can reach, then exit")
    ap.add_argument("--models", default="", help="comma-separated API model ids to compare")
    ap.add_argument("--rubric", default="hq01_url_shortener")
    ap.add_argument("--repeat", type=int, default=1, help="runs per path (these are noisy)")
    ap.add_argument("--thinking", type=int, default=-1,
                    help="thinkingBudget for the API path; -1 leaves it to the model's default")
    ap.add_argument("--skip-agy", action="store_true")
    a = ap.parse_args()

    key = _key()
    if a.list:
        if not key:
            print("No GEMINI_API_KEY found (env or .env).")
            print("Get one at https://aistudio.google.com — it is separate from a Gemini "
                  "subscription, which is the chat product and carries no API access.")
            return 1
        print("Models this key can reach:\n")
        for m in list_models(key):
            print(f"  {m['id']:44} {m['display']:34} in={m['in']:>9} out={m['out']:>7}")
        print("\nThere is no 'gemini-3.6-flash-high' here — that is an Antigravity tier label, not "
              "an API model id. Pick the closest and compare it below.")
        return 0

    prompt = build_prompt(a.rubric)
    print(f"rubric={a.rubric}  prompt={len(prompt)} chars  repeat={a.repeat}\n")

    rows = []
    if not a.skip_agy:
        for i in range(a.repeat):
            raw, took = run_agy(prompt)
            rows.append(summarise(f"agy {AGY_MODEL}", raw, took))
            show(rows[-1])

    models = [m.strip() for m in a.models.split(",") if m.strip()]
    if models and not key:
        print("\nNo API key, so only the agy path ran — a keyless call just 403s and tells you "
              "nothing. Run with --list once you have one.")
        models = []
    for m in models:
        for i in range(a.repeat):
            raw, took = run_api(prompt, key, m, None if a.thinking < 0 else a.thinking)
            r = summarise(f"api {m}", raw, took)
            r["usage"] = dict(LAST_USAGE)
            rows.append(r)
            show(r)

    ok = [r for r in rows if not r.get("error") and r["parsed"]]
    if len(ok) >= 2:
        base = ok[0]
        print(f"\nAgreement against {base['label']} (same rubric points = same score):")
        for r in ok[1:]:
            same_hit = set(r["hit"]) == set(base["hit"])
            same_adv = r["advance"] == base["advance"]
            speed = f"{base['took'] / r['took']:.1f}x faster" if r["took"] else "n/a"
            print(f"  {r['label']:34} hit {'SAME' if same_hit else 'DIFFERS':7}"
                  f"  advance {'same' if same_adv else 'DIFFERS':7}  {speed}")
        print("\nRead the SAY text too — grading agreement is necessary, not sufficient. A path that "
              "grades identically but explains shallowly is still a downgrade.")
        for r in ok:
            print(f"\n--- {r['label']} ---\n{r['say'][:700]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
