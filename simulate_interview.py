#!/usr/bin/env python3
"""Run real interviews against a simulated student, and measure how good they were.

Static analysis can only guess what the scaffolding does to a conversation. This drives the ACTUAL
code path — build_prompt -> Gemini -> apply_turn -> dossier — with a model on the other side playing
a student, and then measures the result. Every failure it finds is a failure that really happened.

The measurement is the point. "The interviewer repeats itself" was a user complaint; here it is a
number, so a fix can be shown to work rather than asserted:

  repeat_rate     fraction of interviewer questions that are near-duplicates of an earlier one
  restate_asks    times it asked the student to repeat something the interviewer itself had said
  stall           longest run of turns spent inside one phase without it closing
  progress        phases actually completed per turn spent

Personas matter more than volume: a strong student never triggers the hint ladder, so a run of only
strong students proves nothing about the paths that were broken.

Usage:
  python3 simulate_interview.py --personas stuck,terse --turns 12
  python3 simulate_interview.py --all --turns 14 --out .bughunt/sim
"""
import argparse
import difflib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "app"))

PERSONAS = {
    "strong": "You know this topic well. Answer correctly, concisely, in your own words — never in "
              "the phrasing an answer key would use. Occasionally add a correct detail that was not "
              "asked for.",
    "weak": "You have read the notes once and remember little. Give vague, partly-wrong answers. "
            "When you cannot answer, say so plainly — 'I don't know', 'I'm stuck'.",
    "stuck": "You are struggling badly today. Say 'I'm stuck' or 'I don't know' to most questions. "
             "Occasionally attempt a guess that is wrong. You want the interviewer to teach you.",
    "terse": "Answer in three words or fewer wherever possible. Never elaborate unless pushed. Your "
             "answers are usually CORRECT, just extremely short.",
    "curious": "You often answer with a question of your own — 'can you explain that with an "
               "example?', 'why does that matter?', 'wait, isn't it the opposite?'. You want to "
               "understand, not just be tested.",
    "tangent": "You answer, then drift into a related topic you find more interesting, and ask "
               "about that instead. You are engaged but hard to keep on rails.",
    "verbose": "You write long, rambling answers that bury a correct point in three paragraphs of "
               "throat-clearing and unrelated context.",
    "contrarian": "You often disagree with the interviewer's framing, sometimes correctly. You "
                  "push back and ask them to justify the question.",
}

CANDIDATE_PROMPT = """You are role-playing a STUDENT in a mock technical interview. You are not an
assistant; do not break character, do not offer to help, do not mention that you are an AI.

YOUR CHARACTER: {persona}

Rules:
- Reply with ONLY what the student would type next. No preamble, no quotes, no stage directions.
- Stay in character even if the interviewer is repetitive or unhelpful — a real student would get
  visibly frustrated, and saying so is in character.
- Keep it to what a person would actually type in a chat box.

THE INTERVIEW SO FAR:
{transcript}

INTERVIEWER JUST SAID:
{last}

Your reply as the student:"""


def _norm(q: str) -> str:
    q = re.sub(r"[^a-z0-9 ]+", " ", (q or "").lower())
    return " ".join(q.split())


def _questions(text: str) -> list[str]:
    return [" ".join(s.split()) for s in re.findall(r"[^.?!\n]*\?", text or "") if len(s) > 25]


def measure(turns: list) -> dict:
    """Turn a transcript into numbers. difflib rather than embeddings: no dependency, and a
    near-duplicate question is a surface-level restatement almost by definition."""
    asked, repeats, restates = [], [], 0
    for t in turns:
        if t["role"] != "interviewer":
            continue
        for q in _questions(t["content"]):
            n = _norm(q)
            for prev in asked:
                if difflib.SequenceMatcher(None, n, prev).ratio() > 0.72:
                    repeats.append(q)
                    break
            asked.append(n)
        low = t["content"].lower()
        if re.search(r"\b(restate|repeat back|say (that )?again|in your own words|recap what)\b", low):
            restates += 1
    # Longest run of consecutive interviewer turns inside one phase.
    stall = run = 0
    prev_phase = None
    for t in turns:
        if t["role"] != "interviewer":
            continue
        run = run + 1 if t.get("phase") == prev_phase else 1
        prev_phase = t.get("phase")
        stall = max(stall, run)
    return {"questions": len(asked), "repeats": len(repeats), "restate_asks": restates,
            "repeat_rate": round(len(repeats) / max(1, len(asked)), 3),
            "longest_stall": stall, "repeat_examples": repeats[:4]}


def _gen(prompt, gemini, tries=6):
    """One model call, riding out the free tier's rate limits rather than aborting the run."""
    for i in range(tries):
        out, err, retry = gemini.generate(prompt)
        if out:
            return out
        wait = retry or (4 * (i + 1))
        print(f"      (retrying in {wait:.0f}s: {(err or '')[:70]})", flush=True)
        time.sleep(min(wait, 65))
    return None


def run_one(persona_name, rubric_id, max_turns, outdir):
    import db
    from interview import context, gemini, rubrics
    from interview import session as iv
    db.connect()
    db.init()
    uid = 90000 + abs(hash(persona_name)) % 1000
    s = iv.start(uid, rubric_id)
    if not s:
        return None
    sid = s["session_id"]
    print(f"  [{persona_name}] {rubric_id} session {sid}", flush=True)

    for turn in range(max_turns):
        raw = _gen(iv.build_prompt(uid, sid), gemini)
        if not raw:
            print("      gave up: interviewer unreachable", flush=True)
            break
        res = iv.apply_turn(uid, sid, raw)
        if res["done"]:
            print(f"      interview COMPLETE after {turn + 1} turns", flush=True)
            break
        vis = [t for t in iv.turns(sid) if t["role"] in ("interviewer", "candidate")]
        script = "\n".join(f"{'INTERVIEWER' if t['role'] == 'interviewer' else 'YOU'}: {t['content']}"
                           for t in vis[-8:])
        reply = _gen(CANDIDATE_PROMPT.format(persona=PERSONAS[persona_name], transcript=script,
                                             last=res["say"]), gemini)
        if not reply:
            print("      gave up: student unreachable", flush=True)
            break
        iv.add_turn(sid, uid, "candidate", reply.strip()[:4000], iv.get(uid, sid)["current_phase"])

    turns = iv.turns(sid)
    m = measure(turns)
    st = iv.get(uid, sid)
    rep = iv.report(uid, sid) or {}
    m.update({"persona": persona_name, "rubric": rubric_id, "session": sid,
              "turns": len(turns), "status": st["status"], "ended_phase": st["current_phase"],
              "hint_tier": st["hint_tier"], "stuck": st["stuck_signals"],
              "score": round((rep.get("scores") or {}).get("overall", 0), 3)})
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, f"{persona_name}_{rubric_id[:24]}.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(f"PERSONA: {persona_name}\nRUBRIC: {rubric_id}\nMETRICS: "
                 f"{json.dumps(m, indent=2)}\n\n")
        for t in turns:
            fh.write(f"--- {t['role'].upper()} [phase={t['phase']}] ---\n{t['content']}\n")
    print(f"      turns={m['turns']:3} repeats={m['repeats']} rate={m['repeat_rate']} "
          f"stall={m['longest_stall']} score={m['score']}", flush=True)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", default="stuck,curious,terse")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--rubrics", default="os_04_cpu_scheduling,02_greedy")
    ap.add_argument("--turns", type=int, default=12)
    ap.add_argument("--out", default=os.path.join(HERE, ".bughunt", "sim"))
    a = ap.parse_args()

    names = list(PERSONAS) if a.all else [p.strip() for p in a.personas.split(",") if p.strip()]
    bad = [n for n in names if n not in PERSONAS]
    if bad:
        print(f"unknown persona(s): {bad}\nknown: {list(PERSONAS)}")
        return 2

    from interview import gemini, rubrics
    if not gemini.available():
        print("No GEMINI_API_KEY — source .env first.")
        return 1
    rids = [r.strip() for r in a.rubrics.split(",") if rubrics.load(r.strip())]
    if not rids:
        print("no valid rubric ids")
        return 1

    print(f"{len(names)} persona(s) x {len(rids)} rubric(s), up to {a.turns} turns each\n")
    results = []
    for rid in rids:
        for n in names:
            try:
                m = run_one(n, rid, a.turns, a.out)
                if m:
                    results.append(m)
            except Exception as e:
                print(f"  [{n}] FAILED: {e}", flush=True)

    print("\n=== summary ===")
    print(f"  {'persona':12} {'rubric':26} {'turns':>5} {'reps':>5} {'rate':>6} "
          f"{'stall':>6} {'score':>6}  status")
    for m in results:
        print(f"  {m['persona']:12} {m['rubric'][:26]:26} {m['turns']:5} {m['repeats']:5} "
              f"{m['repeat_rate']:6} {m['longest_stall']:6} {m['score']:6}  {m['status']}")
    if results:
        tot_q = sum(m["questions"] for m in results)
        tot_r = sum(m["repeats"] for m in results)
        print(f"\n  OVERALL repeat rate: {tot_r}/{tot_q} = {tot_r / max(1, tot_q):.1%}")
        print(f"  worst stall: {max(m['longest_stall'] for m in results)} turns in one phase")
        with open(os.path.join(a.out, "metrics.json"), "w") as fh:
            json.dump(results, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
