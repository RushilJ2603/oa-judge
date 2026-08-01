"""Interview session orchestration — the part that owns judgement.

The division of labour is the whole design: the model produces language and reports which rubric
point ids an answer covered; THIS module decides everything that matters — when a hint is released,
when a phase advances, what a phase scored, and what gets written into the dossier.

Consequences that fall out of that split:
  * a candidate cannot argue their way past a phase, because advancement is a function of stored
    checkoffs, not of the model agreeing;
  * hint escalation is driven by an app-side counter, so a model that wants to be helpful cannot
    skip to tier 3;
  * a phase's open points are only marked "missed" when the phase actually closes, so a candidate
    who circles back and covers a point later in the same phase still gets credit for it.
"""
import datetime
import json

import db

from . import context, dossier, rubrics

# Stuck-signals needed before the next hint tier is authorised. Deliberately >1 so a single hesitant
# turn does not trigger help — an interview where hints arrive too early teaches nothing.
STUCK_PER_TIER = 2
MAX_TIER = 3


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ lifecycle
def start(user_id: int, rubric_id: str, problem_id: str = None) -> dict | None:
    r = rubrics.load(rubric_id)
    if not r:
        return None
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO interview_session (user_id, kind, rubric_id, problem_id, started_at, "
        "status, current_phase, hint_tier, stuck_signals) VALUES (?,?,?,?,?,'active',?,0,0)",
        (user_id, r.get("type", "HLD"), rubric_id, problem_id, _now(), rubrics.first_phase(r)))
    conn.commit()
    sid = cur.lastrowid
    return {"session_id": sid, "rubric_id": rubric_id, "title": r.get("title", ""),
            "type": r.get("type"), "phase": rubrics.first_phase(r),
            "phases": [p["phase"] for p in r.get("phases", [])]}


def get(user_id: int, session_id: int) -> dict | None:
    row = db.connect().execute(
        "SELECT * FROM interview_session WHERE id=? AND user_id=?",
        (session_id, user_id)).fetchone()          # user scoping: friends never read each other's
    return dict(row) if row else None


def turns(session_id: int) -> list[dict]:
    return [dict(r) for r in db.connect().execute(
        "SELECT role, content, phase, hint_tier FROM interview_turn "
        "WHERE session_id=? ORDER BY idx", (session_id,))]


def add_turn(session_id: int, user_id: int, role: str, content: str,
             phase: str = None, hint_tier: int = 0) -> None:
    conn = db.connect()
    n = conn.execute("SELECT COALESCE(MAX(idx), -1) + 1 AS n FROM interview_turn "
                     "WHERE session_id=?", (session_id,)).fetchone()["n"]
    conn.execute("INSERT INTO interview_turn (session_id, user_id, idx, role, phase, content, "
                 "hint_tier, created_at) VALUES (?,?,?,?,?,?,?,?)",
                 (session_id, user_id, n, role, phase, content, hint_tier, _now()))
    conn.commit()


# ------------------------------------------------------------------ prompt building
def build_prompt(user_id: int, session_id: int) -> str | None:
    """Assemble the next turn's prompt. Called by the API when enqueuing a worker job."""
    s = get(user_id, session_id)
    if not s:
        return None
    r = rubrics.load(s["rubric_id"])
    if not r:
        return None
    dos = dossier.render(user_id, exclude_rubric=s["rubric_id"])
    tl = turns(session_id)
    if not tl:
        return context.build_opening(r, dos)
    last = tl[-1]
    answer = last["content"] if last["role"] == "candidate" else ""
    return context.build_turn(r, s["current_phase"], _checkoff_map(session_id, s["current_phase"]),
                              s["hint_tier"], dos, tl[:-1] if answer else tl, answer)


def _checkoff_map(session_id: int, phase: str) -> dict:
    return {r["point_id"]: r["status"] for r in db.connect().execute(
        "SELECT point_id, status FROM interview_checkoff WHERE session_id=? AND phase=?",
        (str(session_id), phase))}


# ------------------------------------------------------------------ applying a model turn
def apply_turn(user_id: int, session_id: int, raw_model_output: str) -> dict:
    """Fold one model response into session state. Returns what the UI should render.

    Everything the model said is treated as a *report*, not a decision: ids are validated against
    the rubric, and advancement/hints/scores are recomputed here.
    """
    s = get(user_id, session_id)
    r = rubrics.load(s["rubric_id"])
    phase = s["current_phase"]
    parsed = context.parse_response(raw_model_output)

    valid = {m["id"] for m in (rubrics.phase(r, phase) or {}).get("must_hit", [])}
    hit = [i for i in parsed["hit"] if i in valid]          # drop anything not in THIS phase
    partial = [i for i in parsed["partial"] if i in valid and i not in hit]

    dossier.record_checkoffs(user_id, session_id, r, phase, hit, partial, [], parsed["evidence"])

    conn = db.connect()
    tier, stuck = s["hint_tier"], s["stuck_signals"]
    if parsed["stuck"]:
        stuck += 1
        # App-side escalation: the model cannot grant itself a deeper hint.
        if stuck >= STUCK_PER_TIER * (tier + 1) and tier < MAX_TIER:
            tier += 1

    # Advancement is a function of stored evidence, never of the model's ADVANCE flag alone.
    score = dossier.phase_score(user_id, session_id, r, phase)
    advanced = False
    if score["core_met"]:
        nxt = rubrics.next_phase(r, phase)
        _close_phase(user_id, session_id, r, phase)
        if nxt:
            phase, tier, stuck, advanced = nxt, 0, 0, True   # hints reset each phase
        else:
            _finish(user_id, session_id, r)
            phase, advanced = None, True

    conn.execute("UPDATE interview_session SET current_phase=?, hint_tier=?, stuck_signals=? "
                 "WHERE id=?", (phase, tier, stuck, session_id))
    conn.commit()

    say = parsed["say"] or "Go on."
    add_turn(session_id, user_id, "interviewer", say, phase, tier)
    return {"say": say, "phase": phase, "hint_tier": tier, "advanced": advanced,
            "phase_score": score, "hit": hit, "partial": partial,
            "done": phase is None}


def _close_phase(user_id: int, session_id: int, rubric: dict, phase: str) -> None:
    """Mark still-open points as missed — only now, so late credit within a phase is possible."""
    seen = _checkoff_map(session_id, phase)
    open_ids = [m["id"] for m in (rubrics.phase(rubric, phase) or {}).get("must_hit", [])
                if m["id"] not in seen]
    if open_ids:
        dossier.record_checkoffs(user_id, session_id, rubric, phase, [], [], open_ids, {})


def _finish(user_id: int, session_id: int, rubric: dict) -> None:
    scores = [dossier.phase_score(user_id, session_id, rubric, p["phase"])
              for p in rubric.get("phases", [])]
    overall = sum(x["score"] for x in scores) / len(scores) if scores else 0.0
    weakest = sorted(scores, key=lambda x: x["score"])[:2]
    summary = (f"{overall:.0%} overall; weakest: "
               + ", ".join(f"{w['phase']} {w['score']:.0%}" for w in weakest))
    db.connect().execute(
        "UPDATE interview_session SET status='done', ended_at=?, score_json=?, summary=? WHERE id=?",
        (_now(), json.dumps({"overall": overall, "phases": scores}), summary, session_id))
    db.connect().commit()


def report(user_id: int, session_id: int) -> dict | None:
    """Post-interview report: per-phase scores plus every miss, with a link back to the source."""
    s = get(user_id, session_id)
    if not s:
        return None
    r = rubrics.load(s["rubric_id"])
    pts = rubrics.all_points(r)
    misses = []
    for row in db.connect().execute(
            "SELECT point_id, phase, status, evidence FROM interview_checkoff "
            "WHERE session_id=? AND status != 'hit'", (str(session_id),)):
        m = pts.get(row["point_id"])
        if m:
            misses.append({"phase": row["phase"], "status": row["status"],
                           "point": m["point"], "your_answer": row["evidence"] or ""})
    return {"session": s, "title": r.get("title", ""),
            "scores": json.loads(s["score_json"]) if s["score_json"] else None,
            "misses": misses, "source": f"_interview/research/…/{s['rubric_id']}.md"}
