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
    # Microseconds, not seconds. rebuild_skills replays evidence in stored order and the EMA is
    # order-dependent, but a whole turn's checkoffs are written in one loop — at second or even
    # millisecond precision they all carry the same timestamp and the replay order is arbitrary.
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


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


def rebuild_skills(user_id: int) -> int:
    """Recompute one user's entire skill model from the checkoffs that still exist.

    Called after a session is deleted. Replaying is the only honest way to undo a deletion: mastery
    is an exponential moving average, so a removed session's outcomes are already folded into the
    stored number and cannot be subtracted — they have to be re-derived from what remains.

    One nuance worth stating: `interview_checkoff` keeps the FINAL ruling per point per session
    (its primary key is (session_id, point_id)), whereas the live path bumps the average on every
    intermediate ruling. So a rebuilt average is not always bit-identical to the pre-deletion one —
    it is the value implied by the surviving evidence, one outcome per point per session, applied in
    chronological order. Deterministic and idempotent: rebuilding twice changes nothing.
    """
    from . import rubrics
    conn = db.connect()
    rows = conn.execute(
        "SELECT rubric_id, point_id, status, evidence, created_at FROM interview_checkoff "
        "WHERE user_id=? ORDER BY created_at ASC, rowid ASC", (user_id,)).fetchall()

    labels: dict[str, str] = {}
    for rid in {r["rubric_id"] for r in rows}:
        for pid, meta in rubrics.all_points(rubrics.load(rid) or {}).items():
            labels[f"{rid}:{pid}"] = (meta.get("point") or "")[:120]

    agg: dict[str, dict] = {}
    for r in rows:
        outcome = OUTCOME.get(r["status"])
        if outcome is None:
            continue
        key = f"{r['rubric_id']}:{r['point_id']}"
        a = agg.get(key)
        if a is None:
            agg[key] = {"mastery": outcome, "tested": 1, "hits": 1 if outcome >= 1.0 else 0,
                        "last": r["created_at"], "ev": r["evidence"] or ""}
        else:
            a["mastery"] = ALPHA * outcome + (1 - ALPHA) * a["mastery"]
            a["tested"] += 1
            a["hits"] += 1 if outcome >= 1.0 else 0
            a["last"] = r["created_at"]
            a["ev"] = r["evidence"] or a["ev"]

    # Replace wholesale rather than patching: any key with no surviving evidence must disappear,
    # not linger at its last value.
    conn.execute("DELETE FROM skill WHERE user_id=?", (user_id,))
    for key, a in agg.items():
        conn.execute(
            "INSERT OR REPLACE INTO skill (user_id, concept_key, label, mastery, times_tested, "
            "times_hit, last_tested_at, last_evidence) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, key, labels.get(key, ""), a["mastery"], a["tested"], a["hits"],
             a["last"], a["ev"]))
    conn.commit()
    return len(agg)


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


def weak_skills(user_id: int, limit: int = 8, exclude_rubrics=(),
                threshold: float = WEAK_MAX) -> list[dict]:
    """Weakest concepts first — the interviewer's job is to find the edge of what you know.

    Concepts from the rubrics this session will visit are excluded: surfacing "you are weak at est2:
    <the point text>" while running that very question hands over the answer.

    EVERY rubric in the loop is excluded, not just the one in play. A mixed round visits several
    topics in sequence, and a weak-area line naming a point from segment 3 previews it just as surely
    as naming one from segment 1 — the same leak phase scoping exists to prevent. This matters more
    than it looks: a weak-spot drill composes its loop from exactly the topics that rank weakest, so
    without this the leak is close to guaranteed rather than incidental.
    """
    if isinstance(exclude_rubrics, str):
        exclude_rubrics = (exclude_rubrics,) if exclude_rubrics else ()
    prefixes = tuple(f"{rid}:" for rid in exclude_rubrics if rid)
    rows = db.connect().execute(
        "SELECT concept_key, label, mastery, times_tested, last_tested_at, last_evidence "
        "FROM skill WHERE user_id=? AND times_tested > 0 AND mastery < ? "
        "ORDER BY mastery ASC, last_tested_at ASC LIMIT ?",
        (user_id, threshold, limit * 4)).fetchall()
    out = []
    for r in rows:
        if prefixes and r["concept_key"].startswith(prefixes):
            continue
        out.append(dict(r))
        if len(out) >= limit:
            break
    return out


def weak_topics(user_id: int, limit: int = 12, threshold: float = WEAK_MAX) -> list[dict]:
    """The weak-spot list the UI shows: whole TOPICS you are shaky on, weakest first.

    `weak_skills` works at the level of individual rubric points, which is right for the prompt and
    useless on screen — "est2 (mastery 40%)" means nothing to a person. This rolls the same evidence
    up to the topic you would actually click on, and reports how many of its points are still weak
    so the number is legible: "3 of 7 points shaky" rather than a bare average.
    """
    from . import rubrics, subjects
    agg: dict[str, dict] = {}
    for r in db.connect().execute(
            "SELECT concept_key, mastery, times_tested, last_tested_at FROM skill "
            "WHERE user_id=? AND times_tested > 0", (user_id,)):
        rid = r["concept_key"].split(":", 1)[0]
        a = agg.setdefault(rid, {"sum": 0.0, "n": 0, "weak": 0, "tested": 0, "last": ""})
        a["sum"] += r["mastery"]
        a["n"] += 1
        a["weak"] += 1 if r["mastery"] < threshold else 0
        a["tested"] += r["times_tested"]
        a["last"] = max(a["last"], r["last_tested_at"] or "")

    out = []
    for rid, a in agg.items():
        mastery = a["sum"] / a["n"]
        if mastery >= threshold:
            continue                        # demonstrably solid — not a weak spot
        d = rubrics.load(rid)
        if not d:
            continue                        # rubric retired since; nothing to click through to
        out.append(subjects.enrich(
            {"id": rid, "title": d.get("title", rid), "mastery": mastery,
             "weak_points": a["weak"], "points": a["n"], "tested": a["tested"],
             "last_tested_at": a["last"], "difficulty": d.get("difficulty", "")}, d))
    out.sort(key=lambda t: (t["mastery"], -t["weight"]))
    return out[:limit]


def topic_progress(user_id: int) -> dict[str, dict]:
    """rubric_id -> what this user has done on that topic. Powers completion state in the catalog.

    Attempted-ness is derived from CHECKOFFS rather than from `interview_session.rubric_id`, because
    a mixed loop stores only the segment it happens to be in — counting sessions by that column would
    credit one topic for a loop that actually covered four.
    """
    out: dict[str, dict] = {}
    for r in db.connect().execute(
            "SELECT concept_key, mastery, last_tested_at FROM skill "
            "WHERE user_id=? AND times_tested > 0", (user_id,)):
        rid = r["concept_key"].split(":", 1)[0]
        t = out.setdefault(rid, {"sum": 0.0, "points": 0, "solid": 0, "last_at": "", "sessions": 0})
        t["sum"] += r["mastery"]
        t["points"] += 1
        t["solid"] += 1 if r["mastery"] >= WEAK_MAX else 0
        t["last_at"] = max(t["last_at"], r["last_tested_at"] or "")
    for r in db.connect().execute(
            "SELECT rubric_id, COUNT(DISTINCT session_id) AS n FROM interview_checkoff "
            "WHERE user_id=? GROUP BY rubric_id", (user_id,)):
        if r["rubric_id"] in out:
            out[r["rubric_id"]]["sessions"] = r["n"]
    for t in out.values():
        t["mastery"] = t.pop("sum") / t["points"] if t["points"] else 0.0
    return out


def behavior(user_id: int) -> list[dict]:
    return [dict(r) for r in db.connect().execute(
        "SELECT trait, value, observations FROM behavior WHERE user_id=? AND observations >= 2 "
        "ORDER BY trait", (user_id,))]


def recent_sessions(user_id: int, limit: int = 3) -> list[str]:
    from . import rubrics
    rows = db.connect().execute(
        "SELECT started_at, kind, rubric_id, summary FROM interview_session "
        "WHERE user_id=? AND status='done' ORDER BY started_at DESC LIMIT ?",
        (user_id, limit)).fetchall()
    out = []
    for r in rows:
        # The topic TITLE, not the corpus id: "Greedy Algorithms" is something the interviewer can
        # refer to out loud, "01_greedy__deep" is an implementation detail leaking into the prompt.
        d = rubrics.load(r["rubric_id"]) or {}
        out.append(f"{r['started_at'][:10]} {r['kind']} {d.get('title') or r['rubric_id']}"
                   + (f" — {r['summary']}" if r["summary"] else ""))
    return out


def render(user_id: int, exclude_rubrics=()) -> str:
    """Everything the interviewer should know about this candidate, compacted for the prompt."""
    from . import context
    return context.render_dossier(
        facts(user_id), weak_skills(user_id, exclude_rubrics=exclude_rubrics),
        behavior(user_id), recent_sessions(user_id))


def topic_recall(user_id: int, rubric_id: str, session_id: int = 0) -> str:
    """Prior attempts at THIS EXACT topic — the one thing a fresh chat can never know.

    Deliberately leak-free. `weak_skills` excludes the current rubric because naming "you are weak on
    est2: <the point text>" would hand the candidate the answer they are about to be asked for. But
    excluding it entirely threw away something a real interviewer would obviously have: the fact that
    you have sat this question before and how it went.

    So this reports COUNTS AND STANCE, never content — how many prior attempts, when, what they
    scored, and how many of the question's points are still shaky. Enough for the interviewer to skip
    the setup you have already heard and to refuse to go easier, with nothing in it that identifies
    which points to steer toward.
    """
    if not rubric_id:
        return ""
    conn = db.connect()
    prior = conn.execute(
        "SELECT started_at, status, score_json FROM interview_session "
        "WHERE user_id=? AND rubric_id=? AND id != ? ORDER BY started_at DESC LIMIT 5",
        (user_id, rubric_id, session_id or -1)).fetchall()
    rows = conn.execute(
        "SELECT mastery FROM skill WHERE user_id=? AND concept_key LIKE ?",
        (user_id, rubric_id + ":%")).fetchall()
    if not prior and not rows:
        return ""

    bits = []
    if prior:
        last = prior[0]
        when = (last["started_at"] or "")[:10]
        scored = ""
        try:
            if last["score_json"]:
                scored = f", scored {json.loads(last['score_json']).get('overall', 0):.0%}"
        except Exception:
            pass
        times = "once" if len(prior) == 1 else f"{len(prior)} times"
        bits.append(f"They have been interviewed on this exact topic {times} before "
                    f"(most recent {when}{scored}).")
    if rows:
        weak = sum(1 for r in rows if r["mastery"] < WEAK_MAX)
        bits.append(f"{weak} of the {len(rows)} points they have been ruled on here are still weak.")
    bits.append("So: skip the long setup they have already heard, and do NOT go easier — the same "
                "ground is still open. This is calibration for you only; never tell them which "
                "points these are, or that you know their prior score.")
    return "PRIOR ATTEMPTS AT THIS TOPIC:\n" + " ".join(bits)


# ------------------------------------------------------------------ behavioural profile (app-owned)
# Every trait is computed from stored rows — never from the model's opinion of the candidate, which
# would be exactly the kind of unfalsifiable praise the whole design exists to avoid.
VERBOSE_CHARS = 600.0          # answer length treated as "fully verbose"; longer just saturates
HINT_SATURATE = 3.0            # stuck-signals per phase treated as maximum hint dependency
PACE_SATURATE = 6.0            # candidate turns per phase treated as maximally slow


def observe_session(user_id: int, session_id: int, phases_walked: int) -> None:
    """Fold one finished interview into the behavioural profile.

    Runs once, at session close, over data already in SQLite. Needs many sessions before it means
    anything — which is precisely why it cannot live in a chat window.
    """
    conn = db.connect()
    answers = [r["content"] for r in conn.execute(
        "SELECT content FROM interview_turn WHERE session_id=? AND role='candidate'",
        (session_id,))]
    if not answers:
        return
    n_ph = max(1, phases_walked)
    row = conn.execute("SELECT stuck_signals FROM interview_session WHERE id=?",
                       (session_id,)).fetchone()
    stuck = (row["stuck_signals"] if row else 0) or 0

    mean_len = sum(len(a) for a in answers) / len(answers)
    record_behavior(user_id, "verbosity", min(1.0, mean_len / VERBOSE_CHARS),
                    f"mean answer {int(mean_len)} chars")
    record_behavior(user_id, "hint_dependency", min(1.0, (stuck / n_ph) / HINT_SATURATE),
                    f"{stuck} stuck signals over {n_ph} phases")
    record_behavior(user_id, "pacing", min(1.0, (len(answers) / n_ph) / PACE_SATURATE),
                    f"{len(answers)} answers over {n_ph} phases")


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
