"""Compose a mixed interview loop — several subjects in one sitting, like a real onsite.

Two ideas drive selection:

* **Exclusion, not inclusion.** Listing everything you want is tedious and you will forget things;
  saying "not system design today" is one click. So a loop spans every subject by default and you
  subtract what you do not want.
* **Weakness first, weighted by what interviews ask.** Among candidate topics, those you have missed
  or never been tested on sort first, and a topic's interview weight breaks ties — so a loop
  gravitates to important material you are shaky on rather than trivia you happen not to have seen.
"""
import random

import db

from . import rubrics, subjects

# Subjects a loop may draw from, in the order an onsite tends to run them.
DEFAULT_POOL = ["os", "dbms", "cpp", "c", "py", "dsa", "cp", "aptitude", "hld", "lld", "sdfound"]

# Named presets. `segments` is how many topics to visit; `phases` how deep to go in each.
# Short segments on purpose: a loop that spends all its time in one topic is not a loop.
SHAPES = {
    "mixed_full":   {"label": "Full loop", "segments": 4, "phases": 3,
                     "exclude": [], "sub": "Anything — fundamentals, DSA, design"},
    "mixed_core":   {"label": "Core mixed", "segments": 3, "phases": 3,
                     "exclude": ["aptitude", "sdfound", "lld"],
                     "sub": "CS fundamentals + DSA + one design"},
    "cs_round":     {"label": "CS fundamentals", "segments": 3, "phases": 4,
                     "exclude": ["hld", "lld", "sdfound", "cp", "dsa", "aptitude"],
                     "sub": "OS · DBMS · C++ · C · Python"},
    "dsa_round":    {"label": "DSA round", "segments": 2, "phases": 4,
                     "exclude": [s for s in DEFAULT_POOL if s not in ("dsa", "cp")],
                     "sub": "Explain your approach, get critiqued"},
    "design_round": {"label": "Design round", "segments": 2, "phases": 4,
                     "exclude": [s for s in DEFAULT_POOL if s not in ("hld", "lld", "sdfound")],
                     "sub": "System design, end to end"},
    "aptitude_round": {"label": "Aptitude round", "segments": 3, "phases": 3,
                       "exclude": [s for s in DEFAULT_POOL if s != "aptitude"],
                       "sub": "Quant, reasoning, puzzles"},
}


def _mastery(user_id: int) -> dict:
    """rubric_id -> mean mastery. Absent = never tested."""
    agg = {}
    for r in db.connect().execute(
            "SELECT concept_key, mastery FROM skill WHERE user_id=?", (user_id,)):
        agg.setdefault(r["concept_key"].split(":", 1)[0], []).append(r["mastery"])
    return {k: sum(v) / len(v) for k, v in agg.items()}


def available_subjects() -> list[dict]:
    """Subjects that actually have rubrics, for the exclusion UI."""
    counts = {}
    for m in rubrics.summaries():
        counts[m["subject"]] = counts.get(m["subject"], 0) + 1
    out = [{"key": k, "label": subjects.subject_label(k), "count": n,
            "order": subjects.SUBJECTS.get(k, {}).get("order", 99)}
           for k, n in counts.items()]
    out.sort(key=lambda s: s["order"])
    return out


def compose(user_id: int, shape: str = "mixed_full", exclude: list = None,
            segments: int = None, phases: int = None, seed: int = None) -> list:
    """Build a plan: [{"rubric_id":..., "phases":[...]}, ...].

    `exclude` overrides the shape's own exclusions, so the UI can offer either a preset or a
    custom "everything except X, Y" loop through one code path.
    """
    spec = SHAPES.get(shape) or SHAPES["mixed_full"]
    excl = set(exclude if exclude is not None else spec["exclude"])
    n_seg = segments or spec["segments"]
    n_ph = phases or spec["phases"]

    pool = [m for m in rubrics.summaries() if m["subject"] not in excl]
    if not pool:
        return []

    rng = random.Random(seed)
    mastery = _mastery(user_id)
    rng.shuffle(pool)                                   # so equal candidates vary run to run
    # Never-tested (-1) first, then weakest; interview weight breaks ties.
    pool.sort(key=lambda m: (mastery.get(m["id"], -1.0), -m["weight"]))

    # Spread across subjects before repeating one — that is what makes a loop feel like a loop.
    # But when the pool is narrow by design (a single-subject round like Aptitude), refusing to
    # repeat a subject would cut the round down to one topic, so fall back to filling from the pool.
    n_subjects = len({m["subject"] for m in pool})
    plan, used_subject = [], set()
    for m in pool:
        if len(plan) >= n_seg:
            break
        if m["subject"] in used_subject and len(used_subject) < min(n_seg, n_subjects):
            continue
        used_subject.add(m["subject"])
        plan.append({"rubric_id": m["id"], "phases": m["phases"][:n_ph]})
    return plan


def from_ids(ids: list, phases: int = 3) -> list:
    """A loop over topics chosen explicitly — what "drill my weak spots" starts.

    Selection is already done by the caller, so this only validates and trims: unknown ids are
    dropped rather than failing the whole loop, and the segment count is capped so a long weak-spot
    list cannot start a two-hour interview by accident.
    """
    plan = []
    for rid in (ids or [])[:6]:
        r = rubrics.load(rid)
        if not r:
            continue
        plan.append({"rubric_id": rid, "phases": [p["phase"] for p in r.get("phases", [])][:phases]})
    return plan


def describe(plan: list) -> str:
    parts = []
    for seg in plan:
        r = rubrics.load(seg["rubric_id"]) or {}
        parts.append(r.get("title", seg["rubric_id"]))
    return " → ".join(parts)


def preview(user_id: int, shape: str) -> dict:
    plan = compose(user_id, shape)
    spec = SHAPES.get(shape, {})
    return {"shape": shape, "label": spec.get("label", shape), "sub": spec.get("sub", ""),
            "preview": describe(plan), "segments": len(plan)}
