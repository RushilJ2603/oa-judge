#!/usr/bin/env python3
"""Corpus-wide audit of the generated rubrics — the check gate_rubric.py cannot do alone.

gate_rubric.py validates each file in isolation (shape, ids, hint tiers, and that every NUMBER
appears in the source). That catches invented figures but not invented *concepts*: a rubric could be
structurally perfect, numerically clean, and still drift into material the research file never
mentions. Since the whole premise is "grounded in YOUR notes", drift is the failure that matters.

So this measures, per rubric, how much of its distinctive technical vocabulary actually occurs in
the source file, and flags the outliers for a human to read.

Usage:  python3 audit_rubrics.py [--min 0.55] [--verbose]
"""
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
IV = os.path.join(ROOT, "problems", "_interview")
RUBRICS = os.path.join(IV, "rubrics")
RESEARCH = os.path.join(IV, "research")

# Words too generic to prove grounding either way.
STOP = set("""the a an and or but if then than that this these those with without within into onto
from for to of in on at by as is are was were be been being it its their there here when where which
who whom whose what how why can could should would may might must will shall do does did done have
has had you your they them we our us not no yes all any both each few more most other some such only
own same so too very just about above below over under again further once during before after while
because until against between through above about across behind beyond plus minus per via using use
used uses need needs needed make makes made get gets got give gives given take takes taken keep keeps
kept put puts set sets sets also every either neither one two three first second next last new old
good bad best worst high low fast slow big small large long short many much less least even still
back down out off up upside apply applies applied avoid avoids ensure ensures state states stated
explain explains describe describes discuss handle handles support supports include includes
candidate interviewer interview answer answers question questions point points phase phases rubric
system design designs designing data value values case cases time times work works working""".split())

WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9_+\-/]{3,}")


def terms(text: str) -> Counter:
    return Counter(w.lower() for w in WORD.findall(text or "") if w.lower() not in STOP)


def source_for(rid: str) -> str | None:
    for sub in ("sd", "cp"):
        p = os.path.join(RESEARCH, sub, rid + ".md")
        if os.path.exists(p):
            return p
    return None


def rubric_text(d: dict) -> str:
    """Only the generated prose — ids, weights and phase names would inflate the score."""
    out = []
    for p in d.get("phases", []):
        out.append(p.get("goal", ""))
        for m in p.get("must_hit", []):
            out += [m.get("point", ""), m.get("evidence_hint", "")]
        out += p.get("probes", [])
        out += [str(v) for v in (p.get("hints") or {}).values()]
    for t in d.get("tradeoffs", []):
        out += [t.get("topic", ""), t.get("strong_answer", "")]
    for g in d.get("gotchas", []):
        out += [g.get("trap", ""), g.get("correction", "")]
    return " ".join(out)


def main():
    args = sys.argv[1:]
    floor = float(args[args.index("--min") + 1]) if "--min" in args else 0.55
    verbose = "--verbose" in args

    files = sorted(f for f in os.listdir(RUBRICS) if f.endswith(".json")) if os.path.isdir(RUBRICS) else []
    if not files:
        sys.exit("no rubrics yet")

    rows, flagged, missing_src = [], [], []
    for f in files:
        rid = f[:-5]
        src = source_for(rid)
        if not src:
            missing_src.append(rid)
            continue
        d = json.load(open(os.path.join(RUBRICS, f), encoding="utf-8"))
        stext = open(src, encoding="utf-8").read().lower()
        rt = terms(rubric_text(d))
        if not rt:
            flagged.append((rid, 0.0, ["empty rubric text"]))
            continue
        # Weight by frequency: a term the rubric leans on repeatedly matters more than a one-off.
        total = sum(rt.values())
        grounded = sum(c for w, c in rt.items() if w in stext)
        score = grounded / total
        ungrounded = sorted((w for w, c in rt.items() if w not in stext and c >= 2),
                            key=lambda w: -rt[w])[:6]
        rows.append((rid, score, ungrounded))
        if score < floor:
            flagged.append((rid, score, ungrounded))

    rows.sort(key=lambda r: r[1])
    scores = [r[1] for r in rows]
    print(f"audited {len(rows)} rubrics")
    print(f"  grounding: min {min(scores):.0%}  median {sorted(scores)[len(scores)//2]:.0%}  "
          f"max {max(scores):.0%}")
    if missing_src:
        print(f"  WARN no source file for: {', '.join(missing_src)}")

    if verbose:
        print("\nlowest 10:")
        for rid, s, ung in rows[:10]:
            print(f"  {s:5.0%}  {rid:44} {' '.join(ung[:4])}")

    if flagged:
        print(f"\nFLAGGED (<{floor:.0%}) — read these against their source:")
        for rid, s, ung in flagged:
            print(f"  {s:5.0%}  {rid}")
            if ung:
                print(f"         off-source terms: {', '.join(ung)}")
        return 1
    print(f"\nAll rubrics >= {floor:.0%} grounded in their source ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
