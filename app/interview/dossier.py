"""The candidate dossier: persistent memory across interviews.

This is the differentiator. A chat window starts cold every session, so you re-establish who you are,
what you already know, and what you got wrong last time. Here that is state, maintained automatically
from rubric evidence, and injected into every turn.

Nothing in here is written by the model. The model reports which rubric point ids an answer covered;
this module turns those ids into mastery numbers. That separation is why a candidate cannot talk
their way into a better profile.
"""
import datetime
import json

import db

# Exponential moving average: recent evidence dominates, old evidence fades but never vanishes.
# 0.4 means one strong showing moves a concept substantially without erasing a history of misses —
# interviews are noisy, so a single lucky answer should not mark a weak concept "known".
ALPHA = 0.4
OUTCOME = {"hit": 1.0, "partial": 0.5, "missed": 0.0}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ writing evidence
def record_checkoffs(user_id: int, session_id: int, rubric: dict, phase: str,
                     hit: list, partial: list, missed: list, evidence: dict) -> None:
    """Persist one turn's rulings and fold them into the skill model.

    `missed` is supplied by the caller (the app derives it from the phase's open points), not by the
    model — a model that simply never mentions a point must not be able to hide a miss.
    """
    conn = db.connect()
    now = _now()
    points = {m["id"]: m for p in rubric.get("phases", []) for m in p.get("must_hit", [])}
    rid = rubric.get("id", "")

    for status, ids in (("hit", hit), ("partial", partial), ("missed", missed)):
        for pid in ids:
            meta = points.get(pid)
            if not meta:
                continue                      # unknown id from the model: ignore, never invent
            ev = (evidence or {}).get(pid, "")
            conn.execute(
                "INSERT OR REPLACE INTO interview_checkoff "
                "(session_id, user_id, rubric_id, phase, point_id, status, evidence, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (str(session_id), user_id, rid, phase, pid, status, ev, now))
            _bump_skill(conn, user_id, f"{rid}:{pid}", meta.get("point", "")[:120],
                        OUTCOME[status], ev, now)
    conn.commit()


def _bump_skill(conn, user_id, key, label, outcome, evidence, now):
    row = conn.execute(
        "SELECT mastery, times_tested, times_hit FROM skill WHERE user_id=? AND concept_key=?",
        (user_id, key)).fetchone()
    if row is None:
        mastery, tested, hits = outcome, 1, (1 if outcome >= 1.0 else 0)
    else:
        mastery = ALPHA * outcome + (1 - ALPHA) * row["mastery"]
        tested = row["times_tested"] + 1
        hits = row["times_hit"] + (1 if outcome >= 1.0 else 0)
    conn.execute(
        "INSERT OR REPLACE INTO skill (user_id, concept_key, label, mastery, times_tested, "
        "times_hit, last_tested_at, last_evidence) VALUES (?,?,?,?,?,?,?,?)",
        (user_id, key, label, mastery, tested, hits, now, evidence or ""))


def record_behavior(user_id: int, trait: str, observed: float, evidence: str = "") -> None:
    """Running mean of a behavioural trait in [0,1]. Needs many sessions to mean anything, which is
    exactly why it cannot live in a chat window."""
    conn = db.connect()
    row = conn.execute("SELECT value, observations FROM behavior WHERE user_id=? AND trait=?",
                       (user_id, trait)).fetchone()
    if row is None:
        val, n = observed, 1
    else:
        n = row["observations"] + 1
        val = row["value"] + (observed - row["value"]) / n
    conn.execute("INSERT OR REPLACE INTO behavior (user_id, trait, value, observations, "
                 "last_evidence, updated_at) VALUES (?,?,?,?,?,?)",
                 (user_id, trait, val, n, evidence, _now()))
    conn.commit()


def set_fact(user_id: int, key: str, value: str) -> None:
    db.connect().execute(
        "INSERT OR REPLACE INTO candidate_fact (user_id, key, value, updated_at) VALUES (?,?,?,?)",
        (user_id, key, value, _now()))
    db.connect().commit()


# ------------------------------------------------------------------ reading it back
def facts(user_id: int) -> list[tuple]:
    return [(r["key"], r["value"]) for r in db.connect().execute(
        "SELECT key, value FROM candidate_fact WHERE user_id=? ORDER BY key", (user_id,))]


# Above this, a concept is considered known and must NOT be labelled a weak area — otherwise the
# interviewer opens by telling you you're shaky on something you demonstrably nailed, which destroys
# trust in the whole dossier faster than any other error.
WEAK_MAX = 0.7


def weak_skills(user_id: int, limit: int = 8, exclude_rubric: str = "",
                threshold: float = WEAK_MAX) -> list[dict]:
    """Weakest concepts first — the interviewer's job is to find the edge of what you know.

    Concepts from the rubric being interviewed right now are excluded: surfacing "you are weak at
    est2" while running that very question would hand over the answer.
    """
    rows = db.connect().execute(
        "SELECT concept_key, label, mastery, times_tested, last_tested_at, last_evidence "
        "FROM skill WHERE user_id=? AND times_tested > 0 AND mastery < ? "
        "ORDER BY mastery ASC, last_tested_at ASC LIMIT ?",
        (user_id, threshold, limit * 3)).fetchall()
    out = []
    for r in rows:
        if exclude_rubric and r["concept_key"].startswith(exclude_rubric + ":"):
            continue
        out.append(dict(r))
        if len(out) >= limit:
            break
    return out


def behavior(user_id: int) -> list[dict]:
    return [dict(r) for r in db.connect().execute(
        "SELECT trait, value, observations FROM behavior WHERE user_id=? AND observations >= 2 "
        "ORDER BY trait", (user_id,))]


def recent_sessions(user_id: int, limit: int = 3) -> list[str]:
    rows = db.connect().execute(
        "SELECT started_at, kind, rubric_id, summary FROM interview_session "
        "WHERE user_id=? AND status='done' ORDER BY started_at DESC LIMIT ?",
        (user_id, limit)).fetchall()
    return [f"{r['started_at'][:10]} {r['kind']} {r['rubric_id']}"
            + (f" — {r['summary']}" if r["summary"] else "") for r in rows]


def render(user_id: int, exclude_rubric: str = "") -> str:
    """Everything the interviewer should know about this candidate, compacted for the prompt."""
    from . import context
    return context.render_dossier(
        facts(user_id), weak_skills(user_id, exclude_rubric=exclude_rubric),
        behavior(user_id), recent_sessions(user_id))


# ------------------------------------------------------------------ scoring (app-owned)
def phase_score(user_id: int, session_id: int, rubric: dict, phase: str) -> dict:
    """Score a phase from stored checkoffs. Computed here, never read from model output."""
    ph = next((p for p in rubric.get("phases", []) if p["phase"] == phase), None)
    if not ph:
        return {"phase": phase, "score": 0.0, "core_met": False}
    rows = {r["point_id"]: r["status"] for r in db.connect().execute(
        "SELECT point_id, status FROM interview_checkoff WHERE session_id=? AND phase=?",
        (str(session_id), phase))}
    total = won = 0.0
    core_met = True
    for m in ph.get("must_hit", []):
        w = 2.0 if m.get("weight") == "core" else 1.0
        total += w
        won += w * OUTCOME.get(rows.get(m["id"], "missed"), 0.0)
        if m.get("weight") == "core" and rows.get(m["id"]) != "hit":
            core_met = False
    return {"phase": phase, "score": (won / total) if total else 0.0, "core_met": core_met}
