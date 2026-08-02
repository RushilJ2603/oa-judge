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

# Stuck-signals needed to reach each hint tier: 1st signal -> tier 1, 3rd -> tier 2, 5th -> tier 3.
# Saying "I'm stuck" must DO something immediately, or the candidate learns that asking for help is
# pointless. Depth is still earned: the deep hints need sustained struggle, not one hesitation.
TIER_AT = (1, 3, 5)
MAX_TIER = 3


def _tier_for(stuck: int) -> int:
    t = 0
    for i, need in enumerate(TIER_AT, start=1):
        if stuck >= need:
            t = i
    return min(t, MAX_TIER)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ lifecycle
def start(user_id: int, rubric_id: str, problem_id: str = None, plan: list = None) -> dict | None:
    """Start a session.

    `plan` (mixed rounds) is a list of {"rubric_id":..., "phases":[...]}. Without it the session is
    a single rubric walked end to end — the original behaviour, unchanged.
    """
    if plan:
        plan = [seg for seg in plan if rubrics.load(seg.get("rubric_id"))]
        if not plan:
            return None
        rubric_id = plan[0]["rubric_id"]
    r = rubrics.load(rubric_id)
    if not r:
        return None
    first = (plan[0]["phases"][0] if plan and plan[0].get("phases") else rubrics.first_phase(r))
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO interview_session (user_id, kind, rubric_id, problem_id, started_at, "
        "status, current_phase, hint_tier, stuck_signals, plan_json, segment_idx) "
        "VALUES (?,?,?,?,?,'active',?,0,0,?,0)",
        (user_id, "MIXED" if plan else r.get("type", "HLD"), rubric_id, problem_id, _now(), first,
         json.dumps(plan) if plan else None))
    conn.commit()
    sid = cur.lastrowid
    return {"session_id": sid, "rubric_id": rubric_id, "title": r.get("title", ""),
            "type": "MIXED" if plan else r.get("type"), "phase": first,
            "phases": _phase_labels(plan, r), "mixed": bool(plan)}


def _phase_labels(plan, r) -> list:
    """What the progress rail shows. For a mixed round the rail spans every segment, so the
    candidate can see the whole loop rather than being surprised by a subject change."""
    if not plan:
        return [p["phase"] for p in r.get("phases", [])]
    out = []
    for seg in plan:
        sr = rubrics.load(seg["rubric_id"]) or {}
        for ph in (seg.get("phases") or [p["phase"] for p in sr.get("phases", [])]):
            out.append(ph)
    return out


def _plan(s) -> list | None:
    try:
        return json.loads(s["plan_json"]) if s.get("plan_json") else None
    except Exception:
        return None


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
    # In a mixed round the subject can change mid-session; the prompt always describes the segment
    # the candidate is actually in, so the interviewer never grades against the previous subject.
    last = tl[-1]
    answer = last["content"] if last["role"] == "candidate" else ""
    # Ship the ORIGINAL notes/research section alongside the rubric. Without it the interviewer can
    # only score a checklist; with it it can engage a tangent, judge a subtle claim, or answer "why"
    # the way someone who has actually read the chapter would. Latency is unaffected — measured, the
    # model call is auth-dominated, not token-dominated (a two-token reply still costs ~14s).
    return context.build_turn(r, s["current_phase"], _checkoff_map(session_id, s["current_phase"]),
                              s["hint_tier"], dos, tl[:-1] if answer else tl, answer,
                              grounding=rubrics.source_text(s["rubric_id"]))


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
        tier = max(tier, _tier_for(stuck))

    # Advancement is a function of stored evidence, never of the model's ADVANCE flag alone.
    score = dossier.phase_score(user_id, session_id, r, phase)
    advanced = False
    rubric_id, seg_idx = s["rubric_id"], s["segment_idx"]
    if score["core_met"]:
        _close_phase(user_id, session_id, r, phase)
        nxt, rubric_id, seg_idx = _next_step(s, r, phase)
        if nxt:
            # New phase = new question, so hints step back — but NOT to zero when the candidate has
            # been struggling. Dropping straight to "no hints" right after they earned help reads as
            # the interviewer taking support away, and they must re-earn it from scratch.
            phase, advanced = nxt, True
            tier = max(0, tier - 1)
            stuck = TIER_AT[tier - 1] if tier > 0 else 0
        else:
            _finish(user_id, session_id, s)
            phase, advanced = None, True

    conn.execute("UPDATE interview_session SET current_phase=?, hint_tier=?, stuck_signals=?, "
                 "rubric_id=?, segment_idx=? WHERE id=?",
                 (phase, tier, stuck, rubric_id, seg_idx, session_id))
    conn.commit()

    say = parsed["say"] or "Go on."
    add_turn(session_id, user_id, "interviewer", say, phase, tier)
    return {"say": say, "say_html": render_md(say), "phase": phase, "hint_tier": tier,
            "advanced": advanced, "phase_score": score, "hit": hit, "partial": partial,
            "done": phase is None}


def render_md(text: str) -> str:
    """Interviewer turns contain code, formulas and lists — render them.

    Reuses the judge's own renderer, which escapes HTML (verified against script/img payloads) and
    converts LaTeX to Unicode, so untrusted model output is safe to inject and `vector<int>`,
    fenced code and O(n^2) all display correctly instead of as literal markdown.
    """
    try:
        from runner import md
        return md.render(text or "")
    except Exception:
        return ""


def _next_step(s, r, phase) -> tuple:
    """Where the interview goes after `phase`: next phase, next segment, or the end.

    Returns (phase|None, rubric_id, segment_idx).
    """
    plan = _plan(s)
    if not plan:
        return rubrics.next_phase(r, phase), s["rubric_id"], 0
    idx = s["segment_idx"]
    seg = plan[idx] if idx < len(plan) else None
    seq = (seg.get("phases") if seg else None) or [p["phase"] for p in r.get("phases", [])]
    if phase in seq and seq.index(phase) + 1 < len(seq):
        return seq[seq.index(phase) + 1], s["rubric_id"], idx        # same subject, next phase
    if idx + 1 < len(plan):                                          # hop to the next subject
        nseg = plan[idx + 1]
        nr = rubrics.load(nseg["rubric_id"]) or {}
        nphases = nseg.get("phases") or [p["phase"] for p in nr.get("phases", [])]
        return (nphases[0] if nphases else None), nseg["rubric_id"], idx + 1
    return None, s["rubric_id"], idx


def _close_phase(user_id: int, session_id: int, rubric: dict, phase: str) -> None:
    """Mark still-open points as missed — only now, so late credit within a phase is possible."""
    seen = _checkoff_map(session_id, phase)
    open_ids = [m["id"] for m in (rubrics.phase(rubric, phase) or {}).get("must_hit", [])
                if m["id"] not in seen]
    if open_ids:
        dossier.record_checkoffs(user_id, session_id, rubric, phase, [], [], open_ids, {})


def _rubrics_in(s) -> list:
    """Every rubric this session touched — one, or all segments of a mixed round."""
    plan = _plan(s)
    ids = [seg["rubric_id"] for seg in plan] if plan else [s["rubric_id"]]
    seen, out = set(), []
    for rid in ids:
        if rid in seen:
            continue
        seen.add(rid)
        r = rubrics.load(rid)
        if r:
            out.append(r)
    return out


def _finish(user_id: int, session_id: int, s) -> None:
    # Score every phase actually walked, across all segments of a mixed round.
    scores = []
    for r in _rubrics_in(s):
        for p in r.get("phases", []):
            sc = dossier.phase_score(user_id, session_id, r, p["phase"])
            if sc["score"] > 0 or _was_walked(session_id, p["phase"]):
                scores.append({**sc, "rubric_id": r["id"]})
    overall = sum(x["score"] for x in scores) / len(scores) if scores else 0.0
    weakest = sorted(scores, key=lambda x: x["score"])[:2]
    summary = (f"{overall:.0%} overall; weakest: "
               + ", ".join(f"{w['phase']} {w['score']:.0%}" for w in weakest))
    db.connect().execute(
        "UPDATE interview_session SET status='done', ended_at=?, score_json=?, summary=? WHERE id=?",
        (_now(), json.dumps({"overall": overall, "phases": scores}), summary, session_id))
    db.connect().commit()


def history(user_id: int, limit: int = 50) -> list[dict]:
    """Past interviews, newest first — every session is already stored, this just surfaces them.

    Includes active/abandoned ones so a session interrupted by the worker dying (WSL down, laptop
    asleep) is visible and resumable rather than silently lost.
    """
    out = []
    for r in db.connect().execute(
            "SELECT id, kind, rubric_id, started_at, ended_at, status, current_phase, score_json, "
            "summary, plan_json FROM interview_session WHERE user_id=? "
            "ORDER BY started_at DESC LIMIT ?", (user_id, limit)):
        s = dict(r)
        rs = _rubrics_in(s)
        title = " + ".join(x.get("title", "") for x in rs) if rs else s["rubric_id"]
        overall = None
        if s["score_json"]:
            try:
                overall = json.loads(s["score_json"]).get("overall")
            except Exception:
                pass
        n_turns = db.connect().execute(
            "SELECT COUNT(*) AS n FROM interview_turn WHERE session_id=? AND role='candidate'",
            (s["id"],)).fetchone()["n"]
        out.append({
            "id": s["id"], "kind": s["kind"], "title": title, "started_at": s["started_at"],
            "ended_at": s["ended_at"], "status": s["status"], "phase": s["current_phase"],
            "overall": overall, "summary": s["summary"], "answers": n_turns,
            "mixed": bool(s["plan_json"]),
        })
    return out


def _was_walked(session_id: int, phase: str) -> bool:
    return bool(db.connect().execute(
        "SELECT 1 FROM interview_checkoff WHERE session_id=? AND phase=? LIMIT 1",
        (str(session_id), phase)).fetchone())


def report(user_id: int, session_id: int) -> dict | None:
    """Post-interview report: per-phase scores plus every miss, with a link back to the source."""
    s = get(user_id, session_id)
    if not s:
        return None
    rs = _rubrics_in(s)
    r = rs[0] if rs else None
    pts = {}
    for rr in rs:
        pts.update(rubrics.all_points(rr))
    misses = []
    for row in db.connect().execute(
            "SELECT point_id, phase, status, evidence FROM interview_checkoff "
            "WHERE session_id=? AND status != 'hit'", (str(session_id),)):
        m = pts.get(row["point_id"])
        if m:
            misses.append({"phase": row["phase"], "status": row["status"],
                           "point": m["point"], "your_answer": row["evidence"] or ""})
    title = (" + ".join(x.get("title", "") for x in rs) if len(rs) > 1
             else (r.get("title", "") if r else ""))
    return {"session": s, "title": title,
            "scores": json.loads(s["score_json"]) if s["score_json"] else None,
            "misses": misses, "source": f"_interview/research/…/{s['rubric_id']}.md"}
