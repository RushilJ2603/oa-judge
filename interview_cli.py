#!/usr/bin/env python3
"""Hold a real interview from the command line, so an agent can BE the student.

Every command drives the production path — build_prompt -> Gemini -> apply_turn -> dossier — so a
conversation here is indistinguishable from one in the browser. That is the point: an auditor
reading source can only guess what the scaffolding does to a conversation; an auditor that sits
through one finds out.

  python3 interview_cli.py topics [filter]        list topics you can be interviewed on
  python3 interview_cli.py start <rubric_id>      begin; prints the session id and first question
  python3 interview_cli.py say <sid> "<answer>"   answer; prints the interviewer's reply
  python3 interview_cli.py show <sid>             the whole transcript so far
  python3 interview_cli.py state <sid>            phase, hint tier, per-point rulings, score
  python3 interview_cli.py report <sid>           the end-of-interview report

Use a scratch database so a simulated session never pollutes real history:
  OAJ_DB=/tmp/probe.db python3 interview_cli.py start os_04_cpu_scheduling
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "app"))

UID = int(os.environ.get("OAJ_CLI_USER", "90001"))


def _ready():
    import db
    db.connect()
    db.init()


def _ask(prompt, tries=3):
    """One interviewer turn, through the SAME routing production uses.

    Not a direct Gemini call: the free tier's quota is small enough that a few probing sessions
    exhaust it, and a probe that dies on a 429 tests nothing. interview_worker.generate() is the
    real dispatcher — API when it is healthy, agy when it is not — so a session here exercises
    exactly what a student would get.
    """
    sys.path.insert(0, HERE)
    import interview_worker as w
    for i in range(tries):
        out, err = w.generate(prompt)
        if out:
            return out
        print(f"[attempt {i + 1} failed: {(err or '')[:110]}]", file=sys.stderr, flush=True)
        time.sleep(3)
    return None


def _turn(sid):
    from interview import session as iv
    raw = _ask(iv.build_prompt(UID, sid))
    if not raw:
        print("ERROR: the interviewer could not be reached.")
        return 1
    res = iv.apply_turn(UID, sid, raw)
    print(res["say"])
    tail = [f"phase={res['phase']}", f"hint_tier={res['hint_tier']}"]
    if res["advanced"]:
        tail.append("PHASE ADVANCED")
    if res["done"]:
        tail.append("INTERVIEW COMPLETE")
    print(f"\n[{'  '.join(tail)}]")
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    _ready()
    from interview import rubrics
    from interview import session as iv

    if cmd == "topics":
        needle = (argv[2].lower() if len(argv) > 2 else "")
        for m in rubrics.summaries():
            if not needle or needle in m["title"].lower() or needle in m["id"].lower():
                print(f"  {m['id']:44} {m['subject_label'][:22]:24} {m['title'][:46]}")
        return 0

    if cmd == "start":
        if len(argv) < 3:
            print("usage: start <rubric_id>")
            return 2
        s = iv.start(UID, argv[2])
        if not s:
            print(f"unknown rubric {argv[2]!r} — try: interview_cli.py topics")
            return 1
        print(f"[session {s['session_id']}]  {s['title']}  phases: {', '.join(s['phases'])}\n")
        return _turn(s["session_id"])

    if cmd == "say":
        if len(argv) < 4:
            print('usage: say <sid> "<your answer>"')
            return 2
        sid = int(argv[2])
        s = iv.get(UID, sid)
        if not s:
            print("unknown session")
            return 1
        if s["status"] != "active":
            print("this interview is already finished")
            return 1
        iv.add_turn(sid, UID, "candidate", " ".join(argv[3:])[:8000], s["current_phase"])
        return _turn(sid)

    if cmd == "show":
        for t in iv.turns(int(argv[2])):
            print(f"--- {t['role'].upper()} [phase={t['phase']}] ---\n{t['content']}\n")
        return 0

    if cmd == "state":
        import db
        from interview import dossier
        sid = int(argv[2])
        s = iv.get(UID, sid)
        if not s:
            print("unknown session")
            return 1
        r = rubrics.load(s["rubric_id"])
        print(f"topic={s['rubric_id']}  status={s['status']}  phase={s['current_phase']}  "
              f"hint_tier={s['hint_tier']}  stuck_signals={s['stuck_signals']}")
        rows = {x["point_id"]: x["status"] for x in db.connect().execute(
            "SELECT point_id, status FROM interview_checkoff WHERE session_id=?", (str(sid),))}
        for p in r.get("phases", []):
            marks = " ".join(f"{m['id']}={rows.get(m['id'], 'open')}" for m in p["must_hit"])
            here = " <- current" if p["phase"] == s["current_phase"] else ""
            print(f"  {p['phase']:16} {marks}{here}")
        if s["current_phase"]:
            print("  score:", json.dumps(dossier.phase_score(UID, sid, r, s["current_phase"])))
        return 0

    if cmd == "report":
        rep = iv.report(UID, int(argv[2]))
        if not rep:
            print("unknown session")
            return 1
        sc = rep.get("scores") or {}
        print(f"{rep['title']} — overall {sc.get('overall', 0):.0%}")
        for p in sc.get("phases", []):
            print(f"  {p['phase']:16} {p['score']:.0%}")
        print("\nmissed:")
        for m in rep.get("misses", []):
            print(f"  [{m['phase']}] {m['point'][:100]}")
            if m["your_answer"]:
                print(f"      you said: {m['your_answer'][:90]}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
