"""Mock OA — a timed paper of 2–4 problems under one clock.

The judge could already time a single problem (`oa_session`), but an OA is a *paper*: three
questions, one deadline, and the skill being tested is triage — which one you open first, when you
abandon Q2 for Q3, whether you leave 40 minutes for the hard one. None of that exists when you solve
one problem at a time with no clock you can lose.

What lives here is the pure part: the curated catalogue, the time model, and paper composition.
Anything that touches the database is in store.py, and the deadline is enforced there — this module
never decides whether a submission counted.

The time model
--------------
`COST_MIN` is how long a problem of each difficulty is *expected* to take a candidate who solves it.
It is what "adjust the number of questions to the difficulty" means in practice: a 3-hour paper is
four questions when two of them are Hard, but five if they are all Medium-ish. It deliberately runs
under the paper length (four questions at 164 estimated minutes for a 180-minute paper) because a
real OA gives you reading, debugging and re-submitting time on top of the solve itself; a paper
budgeted to exactly 100% is a paper nobody finishes.

The curated sets do NOT use this model — their `minutes` is hand-set per set, and the estimate is
shown alongside only as information. The model exists for random papers.
"""
from __future__ import annotations

import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
SETS_PATH = os.path.join(HERE, "mockoa_sets.json")

# Expected solve time per difficulty, in minutes.
COST_MIN = {"Easy": 18, "Medium": 32, "Hard": 50}
DEFAULT_COST = 32

# Paper lengths the UI offers. Any duration in [30, 300] is accepted by the API — these are just
# the buttons, and they are the lengths real OAs actually come in.
DURATIONS = [60, 90, 120, 180]

MIN_QUESTIONS, MAX_QUESTIONS = 2, 4
# A paper may be budgeted this far under / over its length. Under-filling is the safer error, so
# the window is asymmetric.
FILL_LO, FILL_HI = 0.78, 1.14

_cache: dict = {"mtime": None, "data": None}


# --------------------------------------------------------------------------- curated catalogue
def _load() -> dict:
    try:
        mtime = os.path.getmtime(SETS_PATH)
    except OSError:
        return {"sets": []}
    if _cache["mtime"] != mtime:
        with open(SETS_PATH, encoding="utf-8") as f:
            _cache["data"] = json.load(f)
        _cache["mtime"] = mtime
    return _cache["data"] or {"sets": []}


def curated() -> list[dict]:
    return list(_load().get("sets") or [])


def get_set(set_id: str) -> dict | None:
    for s in curated():
        if s.get("id") == set_id:
            return s
    return None


def estimate(difficulties) -> int:
    return sum(COST_MIN.get(d, DEFAULT_COST) for d in difficulties)


# --------------------------------------------------------------------------- random papers
def shapes(minutes: int) -> list[tuple[str, ...]]:
    """Every difficulty ladder that plausibly fills `minutes`.

    A ladder is non-decreasing — papers ramp, and a Hard opener is a paper design bug, not a
    difficulty choice. At least one question must be Medium or Hard so no paper is a warm-up
    round only.
    """
    out = []
    order = ["Easy", "Medium", "Hard"]

    def rec(prefix):
        if len(prefix) >= MIN_QUESTIONS:
            total = estimate(prefix)
            if FILL_LO * minutes <= total <= FILL_HI * minutes and any(d != "Easy" for d in prefix):
                out.append(tuple(prefix))
        if len(prefix) == MAX_QUESTIONS:
            return
        start = order.index(prefix[-1]) if prefix else 0
        for d in order[start:]:
            if estimate(prefix + [d]) <= FILL_HI * minutes:
                rec(prefix + [d])

    rec([])
    return out


def _family(tags: list[str]) -> str:
    """Coarse technique family, used to keep one paper from being three of the same question.

    Deliberately coarse: `dp`/`dynamic-programming`/`knapsack` are one family, because a candidate
    who cannot do DP fails all three and learns one thing instead of three.
    """
    blob = " ".join(tags).lower()
    for family, keys in (
        ("dp", ("dynamic-programming", "dp", "knapsack", "memo", "digit-dp", "bitmask-dp")),
        ("graph", ("graph", "bfs", "dfs", "dijkstra", "topological", "union-find", "dsu", "tree", "flow")),
        ("string", ("string", "palindrome", "substring", "subsequence", "trie", "aho", "parsing")),
        ("greedy", ("greedy", "sorting", "interval", "schedul")),
        ("search", ("binary-search", "two-pointer", "sliding-window", "ternary")),
        ("ds", ("heap", "priority-queue", "stack", "queue", "segment", "fenwick", "ordered-set", "sqrt")),
        ("math", ("math", "number-theory", "combinator", "modular", "probability", "geometry", "digits")),
        ("bits", ("bit-manipulation", "bitmask", "xor")),
        ("matrix", ("matrix", "grid", "prefix-sum")),
    ):
        if any(k in blob for k in keys):
            return family
    return "other"


def compose(pool: list[dict], minutes: int, solved: set[str] | None = None,
            seed: int | None = None, exclude: set[str] | None = None) -> list[dict]:
    """Build a random paper of `minutes` from `pool` (indexed problem rows).

    Prefers problems you have never solved — a mock OA you have already seen the answer to measures
    nothing — but falls back to solved ones rather than returning a short paper. Tries to give every
    question a different technique family, and relaxes that before it relaxes the length.

    Returns the chosen rows in ramp order, or [] if the bank cannot fill this length.
    """
    rng = random.Random(seed)
    solved = solved or set()
    exclude = exclude or set()

    by_diff: dict[str, list[dict]] = {"Easy": [], "Medium": [], "Hard": []}
    for row in pool:
        if not row.get("runnable") or row["id"] in exclude:
            continue
        d = row.get("difficulty")
        if d in by_diff:
            by_diff[d].append(row)

    options = shapes(minutes)
    if not options:
        return []
    # More questions is the more OA-like paper, so weight toward the longer ladders that fit.
    ladder = rng.choices(options, weights=[len(s) ** 2 for s in options], k=1)[0]

    for require_distinct in (True, False):
        for _ in range(60):
            picked: list[dict] = []
            used_ids: set[str] = set()
            used_fams: set[str] = set()
            ok = True
            for d in ladder:
                cands = [r for r in by_diff[d] if r["id"] not in used_ids]
                if require_distinct:
                    fresh = [r for r in cands if _family(r.get("tags") or []) not in used_fams]
                    if fresh:
                        cands = fresh
                    else:
                        ok = False
                        break
                unseen = [r for r in cands if r["id"] not in solved]
                cands = unseen or cands
                if not cands:
                    ok = False
                    break
                row = rng.choice(cands)
                picked.append(row)
                used_ids.add(row["id"])
                used_fams.add(_family(row.get("tags") or []))
            if ok and len(picked) == len(ladder):
                return picked
    return []


# --------------------------------------------------------------------------- scoring
def score_paper(problem_ids: list[str], attempts: list[dict]) -> dict:
    """Turn the submissions made inside the window into a paper result.

    Partial credit is `passed/total` on the best submission, which is how OA platforms actually
    score: a solution that clears 8 of 10 hidden tests is worth more than an empty editor, and
    reporting it as a plain fail hides the near-misses that are the most useful thing in a report.
    """
    per: list[dict] = []
    for pid in problem_ids:
        rows = [a for a in attempts if a["problem_id"] == pid]
        best = 0.0
        best_row = None
        for a in rows:
            total = a.get("total") or 0
            frac = 1.0 if a.get("verdict") == "AC" else ((a.get("passed") or 0) / total if total else 0.0)
            if frac >= best:
                best, best_row = frac, a
        acs = [a for a in rows if a.get("verdict") == "AC"]
        per.append({
            "problem_id": pid,
            "submissions": len(rows),
            "solved": bool(acs),
            "points": round(best * 100),
            "verdict": (best_row or {}).get("verdict"),
            "passed": (best_row or {}).get("passed"),
            "total": (best_row or {}).get("total"),
            "first_ac_at": min((a["created_at"] for a in acs), default=None),
        })
    n = len(problem_ids) or 1
    return {
        "per_problem": per,
        "solved": sum(1 for p in per if p["solved"]),
        "attempted": sum(1 for p in per if p["submissions"]),
        "questions": len(problem_ids),
        "score": round(sum(p["points"] for p in per) / n),
    }
