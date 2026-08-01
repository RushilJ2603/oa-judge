"""Compose a mixed interview loop — several subjects in one sitting, like a real onsite.

Selection is weakness-first: given the candidate's dossier, prefer rubrics whose concepts they have
missed or never been tested on. That is the whole point of keeping a skill model — a chat window
would pick at random or ask you what to practise.
"""
import random

import db

from . import rubrics

# A loop shape: how many segments of each type, and how many phases to spend in each.
# Kept short per segment deliberately — a 45-minute loop that spends all its time in one subject is
# not a loop, and a phase is the smallest unit that still produces a real score.
SHAPES = {
    "cs_round": [("FUND", 3)],                                  # fundamentals viva
    "dsa_round": [("CP", 2)],                                   # technique discussion
    "mixed_short": [("FUND", 2), ("CP", 2)],
    "mixed_full": [("FUND", 2), ("CP", 2), ("HLD", 3)],         # closest to a real onsite
    "design_round": [("HLD", 4)],
}


def _weakness_rank(user_id: int) -> dict:
    """rubric_id -> mean mastery (lower = weaker). Untested rubrics get None and sort first."""
    rows = db.connect().execute(
        "SELECT concept_key, mastery FROM skill WHERE user_id=?", (user_id,)).fetchall()
    agg = {}
    for r in rows:
        rid = r["concept_key"].split(":", 1)[0]
        agg.setdefault(rid, []).append(r["mastery"])
    return {k: sum(v) / len(v) for k, v in agg.items()}


def compose(user_id: int, shape: str = "mixed_full", seed: int = None) -> list:
    """Build a plan: [{"rubric_id":..., "phases":[...]}, ...]."""
    spec = SHAPES.get(shape)
    if not spec:
        return []
    rng = random.Random(seed)
    mastery = _weakness_rank(user_id)
    by_type = {}
    for meta in rubrics.summaries():
        by_type.setdefault(meta["type"], []).append(meta)

    plan, used = [], set()
    for typ, n_phases in spec:
        pool = [m for m in by_type.get(typ, []) if m["id"] not in used]
        if not pool:
            continue
        # Weakest first; never-tested counts as weakest (-1) so new ground is explored.
        rng.shuffle(pool)                       # break ties randomly so loops are not identical
        pool.sort(key=lambda m: mastery.get(m["id"], -1.0))
        pick = pool[0]
        used.add(pick["id"])
        plan.append({"rubric_id": pick["id"], "phases": pick["phases"][:n_phases]})
    return plan


def describe(plan: list) -> str:
    parts = []
    for seg in plan:
        r = rubrics.load(seg["rubric_id"]) or {}
        parts.append(r.get("title", seg["rubric_id"]))
    return " → ".join(parts)
