#!/usr/bin/env python3
"""Quality gate for a SINGLE generated interview rubric (problems/_interview/rubrics/<id>.json).

Nothing enters the rubric corpus unless this returns no errors. The rubric corpus is what makes the
interviewer better than a chat model, so a silently-malformed or invented rubric is worse than no
rubric at all: it would ground the interviewer in something false.

Same discipline as gate_candidate.py — the generator's self-report is never trusted. In particular
`--source` enables the grounding check, which is the one that catches the highest-risk failure mode:
a plausible-sounding number the model invented (see SCHEMA.md rule 8).

Usage:
  python3 gate_rubric.py <rubric.json> [--source <research.md>]
Exit 0 = PASS.
"""
import json
import os
import re
import sys

TOP_KEYS = {"id", "title", "type", "relevance", "difficulty", "prereqs",
            "company_notes", "phases", "tradeoffs", "gotchas"}

PHASE_VOCAB = {
    "HLD": ["requirements", "estimation", "api", "data_model", "architecture", "deep_dives", "bottlenecks"],
    "LLD": ["requirements", "entities", "class_design", "implementation", "extensibility", "concurrency"],
    "CONCEPT": ["fundamentals", "mechanics", "tradeoffs", "application"],
    "CP": ["recognition", "approach", "implementation", "complexity", "pitfalls"],
    # CS fundamentals drawn from the user's own subject notes (OS, DBMS, C++, C, Python, DSA).
    # Same shape as CONCEPT but kept a separate type so the catalog can group "OS / DBMS / C++"
    # apart from the system-design foundations, which are a different kind of round.
    "FUND": ["fundamentals", "mechanics", "tradeoffs", "application"],
}
DIFFICULTY = {"campus", "mid", "senior"}
PID_RE = re.compile(r"^[a-z]{2,4}[0-9]+$")
# 2+ digit runs: single digits are too common to be evidence of anything.
NUM_RE = re.compile(r"\d[\d,]*\.?\d*")


def _norm_num(s):
    return s.replace(",", "").rstrip(".")


def _words(s):
    return set(re.findall(r"[a-z]{4,}", (s or "").lower()))


def check(rubric_path, source_path=None):
    errs, warns = [], []
    try:
        d = json.load(open(rubric_path, encoding="utf-8"))
    except Exception as e:
        return [f"not valid JSON: {e}"], []

    # 1. exact top-level key set
    got = set(d.keys())
    if got != TOP_KEYS:
        if got - TOP_KEYS:
            errs.append(f"unexpected top-level keys: {sorted(got - TOP_KEYS)}")
        if TOP_KEYS - got:
            errs.append(f"missing top-level keys: {sorted(TOP_KEYS - got)}")
        return errs, warns                      # shape is wrong; deeper checks are meaningless

    # 2. id matches the source filename stem
    stem = os.path.splitext(os.path.basename(rubric_path))[0]
    if d["id"] != stem:
        errs.append(f"id {d['id']!r} != filename stem {stem!r}")
    if d["id"] != d["id"].lower():
        errs.append("id must be lowercase")

    typ = d.get("type")
    if typ not in PHASE_VOCAB:
        errs.append(f"type {typ!r} not one of {sorted(PHASE_VOCAB)}")
        return errs, warns
    if d.get("difficulty") not in DIFFICULTY:
        errs.append(f"difficulty {d.get('difficulty')!r} not one of {sorted(DIFFICULTY)}")

    phases = d.get("phases") or []
    if not isinstance(phases, list) or not phases:
        errs.append("phases must be a non-empty array")
        return errs, warns

    vocab = PHASE_VOCAB[typ]
    seen_phase, all_pids, all_points = set(), set(), []

    for i, ph in enumerate(phases):
        tag = f"phases[{i}]"
        name = ph.get("phase")
        # 3. vocabulary + no duplicates
        if name not in vocab:
            errs.append(f"{tag}: phase {name!r} not in {typ} vocabulary {vocab}")
        if name in seen_phase:
            errs.append(f"{tag}: duplicate phase {name!r}")
        seen_phase.add(name)
        if not (ph.get("goal") or "").strip():
            errs.append(f"{tag} ({name}): empty goal")

        mh = ph.get("must_hit") or []
        # 5. minimum substance
        if len(mh) < 2:
            errs.append(f"{tag} ({name}): needs >=2 must_hit, got {len(mh)}")
        if not (ph.get("probes") or []):
            errs.append(f"{tag} ({name}): needs >=1 probe")

        hints = ph.get("hints") or {}
        for tier in ("1", "2", "3"):
            if not str(hints.get(tier, "")).strip():
                errs.append(f"{tag} ({name}): hint tier {tier} missing/empty")

        # 6. at least one core point, else nothing can gate advancement
        if not any((p.get("weight") == "core") for p in mh):
            errs.append(f"{tag} ({name}): no 'core' point — phase can never gate advance")

        for p in mh:
            pid = p.get("id", "")
            # 4. stable, unique, well-formed ids (the model returns these, not prose)
            if not PID_RE.match(pid):
                errs.append(f"{tag} ({name}): bad point id {pid!r} (want e.g. req1)")
            if pid in all_pids:
                errs.append(f"{tag} ({name}): duplicate point id {pid!r}")
            all_pids.add(pid)
            if p.get("weight") not in ("core", "extended"):
                errs.append(f"{tag} ({name}): point {pid} bad weight {p.get('weight')!r}")
            txt = (p.get("point") or "").strip()
            if len(txt) < 15:
                errs.append(f"{tag} ({name}): point {pid} too short to be checkable")
            if not (p.get("evidence_hint") or "").strip():
                warns.append(f"{tag} ({name}): point {pid} has no evidence_hint")
            all_points.append((pid, txt))

    # 7. near-duplicate points (heavy word overlap => the rubric double-counts one idea)
    for a in range(len(all_points)):
        for b in range(a + 1, len(all_points)):
            wa, wb = _words(all_points[a][1]), _words(all_points[b][1])
            if wa and wb:
                ov = len(wa & wb) / min(len(wa), len(wb))
                if ov > 0.75:
                    warns.append(f"near-duplicate points {all_points[a][0]}/{all_points[b][0]} "
                                 f"({ov:.0%} overlap)")

    for fld in ("tradeoffs", "gotchas"):
        if not isinstance(d.get(fld), list):
            errs.append(f"{fld} must be an array")
    for t in (d.get("tradeoffs") or []):
        if not (t.get("topic") and t.get("strong_answer")):
            errs.append("tradeoff needs both topic and strong_answer")
    for g in (d.get("gotchas") or []):
        if not (g.get("trap") and g.get("correction")):
            errs.append("gotcha needs both trap and correction")

    # 8. GROUNDING: every multi-digit number in a point must occur in the source.
    #    This is the check that catches invented figures — the failure mode most likely to
    #    survive human review because a wrong-but-plausible number reads fine.
    if source_path and os.path.exists(source_path):
        src = open(source_path, encoding="utf-8").read()
        src_nums = {_norm_num(m) for m in NUM_RE.findall(src)}
        for pid, txt in all_points:
            for raw in NUM_RE.findall(txt):
                n = _norm_num(raw)
                if len(n.replace(".", "")) >= 2 and n not in src_nums:
                    errs.append(f"UNGROUNDED number {n!r} in point {pid} — not present in source")
    elif source_path:
        warns.append(f"source {source_path} not found — grounding check skipped")
    else:
        warns.append("no --source given — grounding check skipped")

    return errs, warns


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    rubric = args[0]
    source = None
    if "--source" in args:
        source = args[args.index("--source") + 1]
    errs, warns = check(rubric, source)
    name = os.path.basename(rubric)
    for w in warns:
        print(f"  warn  {name}: {w}")
    for e in errs:
        print(f"  FAIL  {name}: {e}")
    if errs:
        print(f"GATE: FAIL ({len(errs)} error(s)) {name}")
        sys.exit(1)
    print(f"GATE: PASS {name}")


if __name__ == "__main__":
    main()
