#!/usr/bin/env python3
"""Generate the interview rubric corpus from the research files, one gated file at a time.

Build-time tooling. The runtime interviewer (agy) is NOT involved here by design: rubrics are
static data, so the production system must never depend on a generator being installed or logged in.

Pipeline per source file:
  1. classify (HLD / LLD / CONCEPT / CP) from the filename
  2. ask Grok for JSON matching SCHEMA.md, read-only (--mode ask: no write/shell tools)
  3. gate_rubric.py, including the grounding check against the source
  4. on failure: ONE retry with the failures fed back in
  5. still failing -> quarantine/ with the reasons. It never reaches the corpus.

Resumable: a source whose rubric already passes the gate is skipped, so an interrupted run costs
nothing. Nothing here trusts the generator's self-report — only the gate decides.

Usage:
  python3 extract_rubrics.py [--only <substr>] [--limit N] [--model M] [--force]
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
IV = os.path.join(ROOT, "problems", "_interview")
RESEARCH = os.path.join(IV, "research")
RUBRICS = os.path.join(IV, "rubrics")
QUAR = os.path.join(IV, "quarantine")
GATE = os.path.join(ROOT, "gate_rubric.py")
MODEL = "cursor-grok-4.5-high"
PY = sys.executable or "python3"

VOCAB = {
    "HLD": ["requirements", "estimation", "api", "data_model", "architecture", "deep_dives", "bottlenecks"],
    "LLD": ["requirements", "entities", "class_design", "implementation", "extensibility", "concurrency"],
    "CONCEPT": ["fundamentals", "mechanics", "tradeoffs", "application"],
    "CP": ["recognition", "approach", "implementation", "complexity", "pitfalls"],
    "FUND": ["fundamentals", "mechanics", "tradeoffs", "application"],
}
# Point-id prefixes per phase, so ids are stable and readable in a transcript (req1, est2, ...).
PREFIX = {
    "requirements": "req", "estimation": "est", "api": "api", "data_model": "dm",
    "architecture": "arch", "deep_dives": "dd", "bottlenecks": "bn",
    "entities": "ent", "class_design": "cd", "implementation": "impl",
    "extensibility": "ext", "concurrency": "conc",
    "fundamentals": "fund", "mechanics": "mech", "tradeoffs": "tr", "application": "app",
    "recognition": "rec", "approach": "appr", "complexity": "cx", "pitfalls": "pit",
}


def is_content(rel):
    """True for research files that describe interview material.

    The research dirs also carry SPEC/meta files (SD_SPEC.md, RESEARCH_SPEC.md,
    INTEGRATIONS_RESEARCH.md) that document how the research itself was generated. They contain no
    interview content, so asking a model to turn them into a rubric burns three attempts and then
    correctly quarantines. Excluding them by naming convention is cheaper and clearer than letting
    the gate reject them.
    """
    if rel.startswith("fund/"):
        return True                      # notes sections are pre-filtered when copied in
    name = os.path.basename(rel)
    return bool(re.match(r"^(hq|lq|h\d|l\d|m\d|\d)", name))


def classify(rel):
    """rel is like 'sd/hq01_url_shortener.md', 'cp/10_dp_1_linear__deep.md', 'fund/os_06_deadlocks.md'."""
    sub, name = rel.split("/", 1)
    if sub == "fund":
        return "FUND"
    if sub == "cp":
        return "CP"
    if name.startswith("hq"):
        return "HLD"
    if name.startswith("lq"):
        return "LLD"
    return "CONCEPT"


def build_prompt(stem, typ, body, failures=None):
    phases = VOCAB[typ]
    pref = ", ".join(f"{p}->{PREFIX[p]}N" for p in phases)
    if typ == "FUND":
        # Subject notes (OS/DBMS/C++/C/Python/DSA) are teaching material, not interview research:
        # they carry no "Interview relevance"/"Prereqs"/"Where it appears" lines. Asking for fields
        # that do not exist in the source is how a model gets nudged into inventing them.
        meta_rules = (
            '- "difficulty": one of "campus", "mid", "senior" — judge how deep the material goes.\n'
            '- "relevance": one line on why this topic gets asked in SDE interviews/OAs.\n'
            '- "prereqs": [] (empty array).\n'
            '- "company_notes": "" (empty string) unless the file names companies.\n'
            '- "title": a clean human topic title (e.g. "Deadlocks", "Virtual memory"), not the filename.')
    else:
        meta_rules = (
            '- "difficulty": one of "campus", "mid", "senior" — judge from the Interview relevance line.\n'
            '- "relevance": one line drawn from the file\'s Interview relevance.\n'
            '- "prereqs": array of ids from the file\'s Prereqs line (empty array if none).\n'
            '- "company_notes": summarize the file\'s "Where it appears" (empty string if absent).')
    p = f"""Convert the research file below into a STRUCTURED INTERVIEW RUBRIC as JSON.

You are producing data for an automated interviewer. It will be machine-validated and REJECTED if it
deviates. Accuracy matters more than richness: a plausible-but-invented detail is worse than omitting it.

TOP-LEVEL KEYS — exactly these 10, nothing added, renamed, or nested elsewhere:
  id, title, type, relevance, difficulty, prereqs, company_notes, phases, tradeoffs, gotchas

FIELD RULES
- "id": exactly "{stem}" (lowercase, verbatim).
- "type": exactly "{typ}".
{meta_rules}

"phases": an array. Use ONLY these phase values, in this order, and only those the file supports:
  {phases}
Each phase object:
  {{"phase": <one of above>,
    "goal": "<one line: what this phase must establish>",
    "must_hit": [{{"id":"<{pref}>", "point":"<one specific checkable claim>",
                  "weight":"core"|"extended",
                  "evidence_hint":"<what a passing answer sounds like>"}}],
    "probes": ["<question an interviewer actually asks here>"],
    "hints": {{"1":"<gentle nudge>", "2":"<structural hint>", "3":"<near-answer>"}}}}

HARD REQUIREMENTS (validated automatically)
- Every phase: >=2 must_hit, >=1 probe, and hint tiers "1","2","3" ALL non-empty and escalating.
- Every phase: at least one point with weight "core".
- Point ids: lowercase prefix + number, unique across the WHOLE file, using the phase prefix above.
- Do not restate the same idea as two points.
- NUMBERS: every number you write in a point MUST appear literally in the research file. Never
  compute, round, or invent a figure. If a number is not in the file, omit it and describe qualitatively.
- "tradeoffs": [{{"topic":"X vs Y","strong_answer":"..."}}]  (from the file's tradeoffs/deep dives)
- "gotchas": [{{"trap":"...","correction":"..."}}]  (from the file's follow-ups/gotchas)

Ground EVERYTHING only in the file. Output ONLY the JSON object — no markdown fences, no commentary.
"""
    if failures:
        p += ("\nYOUR PREVIOUS ATTEMPT WAS REJECTED. Fix exactly these and change nothing else:\n"
              + "\n".join(f"  - {f}" for f in failures) + "\n")
    return p + "\nRESEARCH FILE:\n" + body


def call_grok(prompt, model, timeout=600):
    """Read-only (--mode ask) inside an EMPTY scratch dir.

    Two independent containments, because a bulk job should not be one flag away from touching the
    repo: --mode ask withholds the write/shell tools, and --trust is granted only for a directory
    that is empty by construction. The source text travels in the prompt, so the generator never
    needs filesystem access at all. (--yolo is deliberately not used.)
    """
    sandbox = os.path.join(IV, ".genwork")
    os.makedirs(sandbox, exist_ok=True)
    try:
        r = subprocess.run(
            ["cursor-agent", "-p", "--trust", "--mode", "ask", "--model", model, prompt],
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, cwd=sandbox)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if r.returncode != 0:
        return None, f"cursor-agent exit {r.returncode}: {(r.stderr or '')[:200]}"
    return r.stdout, None


def extract_json(text):
    """Pull the JSON object out of a model response.

    Observed failure mode: the generator is non-deterministic and sometimes wraps the object in
    fences or a sentence of preamble. A naive find('{')/rfind('}') breaks when trailing prose also
    contains braces, so the last resort walks the string and returns the first BALANCED object
    (string-aware, so braces inside values don't miscount).
    """
    if not text:
        return None
    t = text.strip()
    try:                                            # 1. already clean
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", t, re.S)   # 2. fenced
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 3. Scan for balanced objects and pick the RUBRIC, not merely the first object.
    #    Observed: a response can lead with a single phase object (or an illustrative fragment)
    #    before the real rubric. Taking the first balanced object then yields a structurally valid
    #    but wrong document, which the gate rejects as "unexpected top-level keys" — three times in
    #    a row, quarantining a file that was never actually bad. So collect every candidate and
    #    prefer one that looks like a rubric; fall back to the largest.
    best = None
    for start in (i for i, c in enumerate(t) if c == "{"):
        depth, in_str, esc = 0, False, False
        for k in range(start, len(t)):
            c = t[k]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(t[start:k + 1])
                    except Exception:
                        break
                    if isinstance(obj, dict):
                        if "phases" in obj and "id" in obj:
                            return obj                  # unambiguous rubric
                        if best is None or len(t[start:k + 1]) > best[0]:
                            best = (len(t[start:k + 1]), obj)
                    break
    return best[1] if best else None


def gate(path, source):
    r = subprocess.run([PY, GATE, path, "--source", source], capture_output=True, text=True)
    fails = [ln.split(": ", 1)[1] for ln in r.stdout.splitlines() if ln.strip().startswith("FAIL")]
    return r.returncode == 0, fails, r.stdout


def process(rel, model, force=False):
    stem = os.path.splitext(os.path.basename(rel))[0]
    src = os.path.join(RESEARCH, rel)
    out = os.path.join(RUBRICS, stem + ".json")
    if os.path.exists(out) and not force:
        ok, _, _ = gate(out, src)
        if ok:
            return "skip", stem, []
    typ = classify(rel)
    body = open(src, encoding="utf-8").read()

    # 3 attempts, not 2: the generator is non-deterministic and an unparseable response is a
    # transient miss (verified — the same input parsed cleanly on the next call). Two attempts let a
    # double-miss quarantine a file that was never actually bad.
    failures = None
    for attempt in (1, 2, 3):
        text, err = call_grok(build_prompt(stem, typ, body, failures), model)
        if err:
            failures = [err]
            continue
        d = extract_json(text)
        if d is None:
            failures = ["output was not parseable JSON — emit ONLY the JSON object"]
            continue
        with open(out, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
        ok, fails, _ = gate(out, src)
        if ok:
            return ("pass" if attempt == 1 else "pass-retry"), stem, []
        failures = fails
        os.remove(out)                              # never leave a failing rubric in the corpus
    # quarantine: never let a failing rubric sit in the corpus
    if os.path.exists(out):
        os.replace(out, os.path.join(QUAR, stem + ".json"))
    with open(os.path.join(QUAR, stem + ".reasons.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(failures or ["unknown"]))
    return "quarantine", stem, failures or []


def main():
    args = sys.argv[1:]
    only = args[args.index("--only") + 1] if "--only" in args else None
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    model = args[args.index("--model") + 1] if "--model" in args else MODEL
    force = "--force" in args

    os.makedirs(RUBRICS, exist_ok=True)
    os.makedirs(QUAR, exist_ok=True)
    todo = []
    for sub in ("sd", "cp", "fund"):
        d = os.path.join(RESEARCH, sub)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if n.endswith(".md") and is_content(f"{sub}/{n}"):
                rel = f"{sub}/{n}"
                if not only or only in rel:
                    todo.append(rel)
    if limit:
        todo = todo[:limit]

    tally = {}
    for i, rel in enumerate(todo, 1):
        status, stem, fails = process(rel, model, force)
        tally[status] = tally.get(status, 0) + 1
        mark = {"pass": "ok", "pass-retry": "ok(retry)", "skip": "--", "quarantine": "QUARANTINE"}[status]
        print(f"[{i}/{len(todo)}] {mark:10} {stem}", flush=True)
        for f in fails[:3]:
            print(f"           ! {f}", flush=True)
    print("\n" + "=" * 60)
    print("SUMMARY: " + "  ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    print(f"corpus: {len([x for x in os.listdir(RUBRICS) if x.endswith('.json')])} rubrics")
    q = len([x for x in os.listdir(QUAR) if x.endswith('.json')])
    if q:
        print(f"QUARANTINED: {q} — review problems/_interview/quarantine/")
    return 1 if tally.get("quarantine") else 0


if __name__ == "__main__":
    sys.exit(main())
