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
import re

import db

from . import context, dossier, rubrics

# Stuck-signals needed to reach each hint tier: 1st signal -> tier 1, 3rd -> tier 2, 5th -> tier 3.
# Saying "I'm stuck" must DO something immediately, or the candidate learns that asking for help is
# pointless. Depth is still earned: the deep hints need sustained struggle, not one hesitation.
TIER_AT = (1, 3, 5)
MAX_TIER = 3


# An explicit "I'm stuck" must work on the turn it is typed, not the turn after.
#
# The stuck counter is only updated once the MODEL has replied and reported STUCK, so a candidate
# asking for help got "NO HINTS AUTHORISED YET" on that very turn and help only on the next one.
# Two audit agents flagged the result from real transcripts: help-seeking is stonewalled, the next
# question is harder, and the student learns that asking is pointless.
#
# So the app reads the request itself. Deliberately narrow — explicit statements of being unable to
# proceed, NOT "can you give an example?" or "why does that matter?", which are curiosity and are
# answered without spending a hint tier.
_ASKING_FOR_HELP = re.compile(
    r"\b(i(?:'|’)?m stuck|i am stuck|i(?:'|’)?m lost|i don(?:'|’)?t know|i dont know|no idea|"
    r"not a clue|i give up|give me (?:a |the )?hint|can i (?:get|have) a hint|hint please|"
    r"help me out|can you help|i(?:'|’)?m blanking|drawing a blank)\b", re.I)


def asked_for_help(text: str) -> bool:
    return bool(_ASKING_FOR_HELP.search(text or ""))


def _tier_for(stuck: int) -> int:
    t = 0
    for i, need in enumerate(TIER_AT, start=1):
        if stuck >= need:
            t = i
    return min(t, MAX_TIER)


def _now():
    # Microseconds, not seconds: history sorts by last interaction, so the ordering key has to be
    # finer-grained than the events it orders. ISO-8601 still sorts lexicographically, and rows
    # already stored at second precision compare correctly against these.
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


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
            "type": "MIXED" if plan else r.get("type"), "phase": first, "step": 0,
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


def step_index(s, r, phase: str) -> int:
    """Absolute position in the flattened progress rail.

    The rail spans every segment of a mixed round, and segments of the same type repeat their phase
    names — "recognition, approach, implementation" three times over for a three-topic CP loop. The
    UI cannot therefore locate the current step by looking the phase name up in the list: it would
    find the first match and highlight segment 1 while the candidate is in segment 3. So the server,
    which knows the segment index, hands over the position directly.
    """
    plan = _plan(s)
    if not plan:
        names = [p["phase"] for p in (r or {}).get("phases", [])]
        return names.index(phase) if phase in names else 0
    offset = 0
    for i, seg in enumerate(plan):
        sr = rubrics.load(seg["rubric_id"]) or {}
        names = seg.get("phases") or [p["phase"] for p in sr.get("phases", [])]
        if i == s["segment_idx"]:
            return offset + (names.index(phase) if phase in names else 0)
        offset += len(names)
    return offset


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


def turns_for_ui(session_id: int) -> list[dict]:
    """Transcript for the browser, with interviewer turns rendered.

    Only the raw markdown is stored, and it is rendered at apply-time for the live turn — so a
    REOPENED interview used to show every past interviewer turn as literal markdown (`**bold**`,
    fenced blocks, `$…$` math). Rendering here means resuming looks identical to living through it.
    Candidate turns stay plain text on purpose: their own input is never treated as markup.
    """
    out = []
    for t in turns(session_id):
        t = dict(t)
        if t["role"] == "interviewer":
            t["html"] = render_md(t["content"])
        out.append(t)
    return out


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
    # Exclude every topic this session will visit, not just the live one — see weak_skills.
    dos = dossier.render(user_id, exclude_rubrics=_rubric_ids(s))
    # Prior attempts at THIS topic are excluded from the dossier (naming a weak point of the live
    # question leaks its answer), so they are re-added here as counts only — see topic_recall.
    recall = dossier.topic_recall(user_id, s["rubric_id"], session_id)
    tl = turns(session_id)
    if not tl:
        return context.build_opening(r, dos, recall)
    # In a mixed round the subject can change mid-session; the prompt always describes the segment
    # the candidate is actually in, so the interviewer never grades against the previous subject.
    last = tl[-1]
    answer = last["content"] if last["role"] == "candidate" else ""
    # Ship the ORIGINAL notes/research section alongside the rubric. Without it the interviewer can
    # only score a checklist; with it it can engage a tangent, judge a subtle claim, or answer "why"
    # the way someone who has actually read the chapter would. Latency is unaffected — measured, the
    # model call is auth-dominated, not token-dominated (a two-token reply still costs ~14s).
    # Tell the model when this is the last phase there is, so it can close rather than end the
    # interview on a question the student will never get to answer.
    nxt, _rid, _seg = _next_step(s, r, s["current_phase"])
    # If they just said they are stuck, release the tier NOW rather than one turn late.
    tier = s["hint_tier"]
    if answer and asked_for_help(answer):
        tier = max(tier, _tier_for(s["stuck_signals"] + 1))
    return context.build_turn(r, s["current_phase"], _checkoff_map(session_id, s["current_phase"]),
                              tier, dos, tl[:-1] if answer else tl, answer,
                              grounding=rubrics.source_text(s["rubric_id"]), recall=recall,
                              is_last=(nxt is None))


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

    # Credit a point wherever it lives in the rubric, not only in the phase currently open.
    #
    # This used to be filtered to the CURRENT phase, and it threw away correct answers. The sequence
    # is ordinary: the interviewer asks about a point, the student's reply also settles the phase's
    # last core point, the phase advances — and then the answer they were still typing lands against
    # a phase that no longer accepts that id. The credit was dropped silently and the point was
    # written up as MISSED, so the report told a student they got wrong something they got right.
    # Four independent audit agents hit this in real interviews before it was reproduced here.
    #
    # Which phase a point belongs to is OUR filing system, not the student's problem. Ids are still
    # checked against the rubric, so the model cannot invent one; they are just recorded against
    # their own phase. INSERT OR REPLACE means late credit overwrites an earlier miss, which is the
    # same "circle back and still get credit" rule the phase-close logic already relies on.
    all_pts = rubrics.all_points(r)
    hit = [i for i in parsed["hit"] if i in all_pts]
    partial = [i for i in parsed["partial"] if i in all_pts and i not in hit]

    by_phase: dict[str, tuple[list, list]] = {}
    for i in hit:
        by_phase.setdefault(all_pts[i]["phase"], ([], []))[0].append(i)
    for i in partial:
        by_phase.setdefault(all_pts[i]["phase"], ([], []))[1].append(i)
    for ph, (h, p) in by_phase.items():
        dossier.record_checkoffs(user_id, session_id, r, ph, h, p, [], parsed["evidence"])

    # Points the interviewer EXPLAINED because the candidate could not get there. Recorded as missed
    # — no credit, so reporting one can never inflate a score — but recorded, which is what matters:
    # an unrecorded point stays "open" forever, the phase can never close, and the interview circles
    # back to a question it already answered itself. That is exactly what happened in real sessions.
    # Gated on the candidate having actually asked for help, so it cannot be used to skip a phase
    # that was never attempted.
    # TAUGHT stays scoped to the CURRENT phase: it closes points out, and letting it reach a later
    # phase would let the interview skip material the student has not seen yet.
    # It also must never DOWNGRADE a ruling. A point already recorded hit or partial has been earned;
    # re-teaching it later (or teaching around it) must not rewrite that to missed and take the
    # credit back — a student praised in the conversation was finishing with it marked wrong.
    here = {m["id"] for m in (rubrics.phase(r, phase) or {}).get("must_hit", [])}
    already = _checkoff_map(session_id, phase)
    taught = [i for i in parsed["taught"] if i in here and i not in hit and i not in partial
              and already.get(i) not in ("hit", "partial")]
    if taught and (s["hint_tier"] > 0 or parsed["stuck"]):
        dossier.record_checkoffs(user_id, session_id, r, phase, [], [], taught, {})

    conn = db.connect()
    tier, stuck = s["hint_tier"], s["stuck_signals"]
    # The app counts an explicit request itself rather than waiting to be told. build_prompt already
    # releases the tier on the turn they ask; without matching it here the STORED tier stays 0, so
    # the composer keeps saying "no hints yet — say if you are stuck" to someone who just did, and
    # they have to ask again next turn to get the same help.
    recent = turns(session_id)
    said = next((t["content"] for t in reversed(recent) if t["role"] == "candidate"), "")
    if parsed["stuck"] or asked_for_help(said):
        stuck += 1
        # App-side escalation: the model cannot grant itself a deeper hint.
        tier = max(tier, _tier_for(stuck))
        # And an app-side FLOOR that does not depend on the model cooperating. TAUGHT is the clean
        # path out of a stalled phase, but a model that simply never emits it would keep the phase
        # open forever and go on re-asking — which is the behaviour being fixed. Once the deepest
        # hint has been released and the candidate is STILL stuck, the phase has nothing left to
        # offer: close its open points as misses and let the interview move on.
        if tier >= MAX_TIER and stuck > TIER_AT[-1]:
            _close_phase(user_id, session_id, r, phase)

    # Advancement is a function of stored evidence, never of the model's ADVANCE flag alone.
    score = dossier.phase_score(user_id, session_id, r, phase)
    advanced = False
    rubric_id, seg_idx = s["rubric_id"], s["segment_idx"]
    # Advance when every core point is hit, OR when none is still open. Requiring `hit` alone was
    # the bug behind "it keeps asking me the same thing": a point the interviewer had explained in
    # full was never hit, so the phase could not close, so it kept coming back to it. A phase with
    # nothing left to ask must move on — the score already reflects what was and was not earned.
    if score["core_met"] or not score["core_open"]:
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
    step = step_index({**s, "segment_idx": seg_idx}, rubrics.load(rubric_id), phase) if phase else -1
    return {"say": say, "say_html": render_md(say), "phase": phase, "step": step,
            "hint_tier": tier, "advanced": advanced, "phase_score": score, "hit": hit,
            "partial": partial, "done": phase is None}


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


def _rubric_ids(s) -> list[str]:
    """Every rubric id this session touches — the live one, or all segments of a mixed round."""
    plan = _plan(s)
    ids = [seg["rubric_id"] for seg in plan] if plan else []
    if s.get("rubric_id") and s["rubric_id"] not in ids:
        ids.append(s["rubric_id"])
    return ids


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
    # HOW they interviewed, not just what they knew. Derived from stored turns and the app's own
    # stuck counter — the model never gets a vote on its own candidate's habits.
    dossier.observe_session(user_id, session_id, len(scores))


def history(user_id: int, limit: int = 50) -> list[dict]:
    """Past interviews, MOST RECENTLY TALKED TO first.

    Ordering by started_at was wrong in the way that actually bites: pick up a three-week-old
    interview, talk to it for twenty minutes, and it stays buried under sessions you have not opened
    since. The list is a conversation list, so it sorts by last interaction — the timestamp of the
    newest turn, falling back to ended_at/started_at for a session with no turns yet.

    Includes active/abandoned ones so a session interrupted by the worker dying (WSL down, laptop
    asleep) is visible and resumable rather than silently lost.
    """
    out = []
    for r in db.connect().execute(
            "SELECT s.id, s.kind, s.rubric_id, s.started_at, s.ended_at, s.status, "
            "       s.current_phase, s.score_json, s.summary, s.plan_json, "
            "       COALESCE((SELECT MAX(t.created_at) FROM interview_turn t "
            "                  WHERE t.session_id = s.id), s.ended_at, s.started_at) AS last_at "
            "FROM interview_session s WHERE s.user_id=? "
            "ORDER BY last_at DESC, s.id DESC LIMIT ?", (user_id, limit)):
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
            "ended_at": s["ended_at"], "last_at": s["last_at"], "status": s["status"],
            "phase": s["current_phase"], "overall": overall, "summary": s["summary"],
            "answers": n_turns, "mixed": bool(s["plan_json"]),
        })
    return out


def delete(user_id: int, session_id: int) -> bool:
    """Erase an interview and every trace it left in the dossier.

    "Deleted" has to mean deleted, or the feature is a lie: a session you removed must not keep
    steering what the interviewer thinks you are weak at. So this is a hard delete of the session,
    its transcript, its rubric evidence and any queued work — followed by a full rebuild of the
    skill model from the evidence that SURVIVED. Filtering at read time would have been cheaper and
    wrong, because mastery is an accumulated average: the deleted session's contribution is already
    baked into the number and only a replay can take it back out.

    Scoped by user_id at every step, so one friend can never delete another's history.
    """
    conn = db.connect()
    if not conn.execute("SELECT 1 FROM interview_session WHERE id=? AND user_id=?",
                        (session_id, user_id)).fetchone():
        return False
    conn.execute("DELETE FROM interview_turn WHERE session_id=? AND user_id=?",
                 (session_id, user_id))
    conn.execute("DELETE FROM interview_checkoff WHERE session_id=? AND user_id=?",
                 (str(session_id), user_id))
    conn.execute("DELETE FROM interview_job WHERE session_id=? AND user_id=?",
                 (session_id, user_id))
    conn.execute("DELETE FROM interview_session WHERE id=? AND user_id=?", (session_id, user_id))
    conn.commit()
    dossier.rebuild_skills(user_id)
    return True


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
