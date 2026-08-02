#!/usr/bin/env python3
"""Fan Grok out over the interview subsystem to find real defects, in safe batches.

Why batched: 9 GB of RAM and 4 cores. Running the whole fleet at once is how the WSL VM got
OOM-killed before, so concurrency is capped and every task is given a hard timeout.

Why narrow tasks: one agent told to "find bugs in the interview system" returns generic advice about
error handling. An agent told to audit ONE file for ONE class of defect, and forbidden from
reporting style opinions, returns things worth checking.

IMPORTANT: nothing here is trusted. Every finding is a LEAD to verify by reading the code and
writing a failing test. Grok has been observed reporting confident, wrong findings — and reporting
"issues" that the code explicitly handles two lines further down.

Usage:
  python3 hunt_bugs.py --batch 5 --timeout 240          # all tasks
  python3 hunt_bugs.py --only context,session           # a subset
  python3 hunt_bugs.py --list                           # show the plan
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, ".bughunt")
MODEL = os.environ.get("OAJ_HUNT_MODEL", "cursor-grok-4.5-high")

# THE BAR. This system exists only to beat one alternative: opening a single Gemini chat, pasting in
# the student's own notes, and saying "interview me". That baseline is fluent, follows the
# conversation naturally, and never repeats itself. Everything here — rubrics, phases, hint tiers,
# scoring, compaction — is SCAFFOLDING added on top, and every piece of it is a chance to be WORSE
# than the baseline.
#
# So the audit question is not "is there a bug". It is: WHERE DOES THE SCAFFOLDING MAKE THE INTERVIEW
# WORSE THAN AN UNSCAFFOLDED CHAT WOULD BE?
#
# A real example already found and fixed, to calibrate what counts: a point the interviewer explained
# was never recorded, so the phase could not close, so it kept re-asking a question it had itself
# answered — until the student typed "you're asking the same question again". A plain chat would
# never do that. The machinery caused it. Findings of that shape are what this hunt is for.
CONTRACT = """\
The system under audit is a mock-interview engine for a student preparing for real technical
interviews. It wraps a language model in scaffolding: a rubric of points per topic, ordered phases,
hint tiers released on a stuck counter, app-side scoring, and a compacted transcript.

THE BAR IT MUST BEAT: one plain chat session with the same model, given the student's notes and a
system prompt saying "interview me on this". That baseline is fluent, responsive to what the student
actually says, and never repeats itself. If any scaffolding here makes the conversation stiffer,
more repetitive, less responsive, or less useful to a student than that baseline, THAT IS THE BUG —
even if every line of code is working exactly as written.

Judge everything by: would this make a student better prepared, and would it feel like talking to a
good interviewer?

Concrete failure shapes that count:
  Q1 REPETITION   asking again what was already asked, answered, or explained. Asking a student to
                  restate something the interviewer itself just said.
  Q2 DEAFNESS     ignoring what the student actually wrote — their question, their confusion, their
                  correct-but-differently-worded answer, a tangent worth following.
  Q3 RIGIDITY     marching through a checklist when a human would follow the conversation; refusing
                  to engage with something interesting because no rubric point names it.
  Q4 MISGRADING   marking a right answer wrong (or wrong answer right) because of wording, partial
                  credit that never resolves, or a point that can never be earned.
  Q5 WHIPLASH     abrupt, unexplained changes of topic, phase or subject; an ending that arrives
                  with no summary; a hint that arrives after the student has already moved on.
  Q6 UNHELPFUL    stonewalling a genuinely stuck student, explaining at the wrong depth, or teaching
                  something the student already demonstrated they know.
  Q7 AMNESIA      losing something the student said earlier that a human interviewer would have
                  remembered and used.

Also still bugs, but SECONDARY here — only report these if they are severe:
  S1 leaks of later-phase content or rubric answers into the prompt or the student's view
  S2 a score or phase advance that a student's typed text can move
  S3 cross-user data exposure, or a lost answer
"""

TASKS = []


def add(area, path, focus, mode="audit", persona="", rubric=""):
    TASKS.append({"id": f"{area}-{len(TASKS):02d}", "area": area, "path": path, "focus": focus,
                  "mode": mode, "persona": persona, "rubric": rubric})


# ---- SIT THROUGH ONE. The most valuable agents in the fleet: they hold a real interview through
# the production code path and report what it was actually like, rather than guessing from source.
PERSONAS = {
    "strong":     "You know the topic well. Answer correctly and concisely IN YOUR OWN WORDS, never "
                  "in textbook phrasing. Sometimes add a correct detail nobody asked for.",
    "stuck":      "You are struggling. Say 'I'm stuck' or 'I don't know' to most questions. "
                  "Occasionally guess wrong. You want to be TAUGHT, not just tested.",
    "terse":      "Answer in three words or fewer. Your answers are usually CORRECT, just extremely "
                  "short. Never elaborate unless pushed.",
    "curious":    "Often answer with a question of your own: 'can you give an example?', 'why does "
                  "that matter?', 'wait, isn't it the opposite?'. You want to understand.",
    "tangent":    "Answer, then drift to a related thing you find more interesting and ask about "
                  "THAT instead. Engaged but hard to keep on rails.",
    "contrarian": "Push back on the framing, sometimes correctly. Ask the interviewer to justify "
                  "the question before you answer it.",
    "verbose":    "Write long rambling answers that bury one correct point in three paragraphs.",
    "returning":  "You have interviewed on this before. Reference that ('we covered this last "
                  "time'), get impatient with basics, and ask to go deeper.",
}
# Three shapes on purpose: notes-derived CS fundamentals, a CP pattern, and an HLD design — they
# fail differently, and a fleet that only ever sits one kind of interview proves little.
TOPICS = ["os_04_cpu_scheduling", "02_greedy", "hq01_url_shortener"]
for _t in TOPICS:
    for _p in PERSONAS:
        add("live", _t, "", mode="interview", persona=_p, rubric=_t)


# The bulk of interview QUALITY lives in the prompt text and the flow rules, not in plumbing —
# so that is where most of the fleet is pointed.

# ---- the role contract: what the interviewer is told to be ---------------------------
for f in ["Read the ROLE contract string. A student pasting their notes into a plain chat gets a "
          "fluent, responsive interviewer for free. Find instructions here that make it WORSE than "
          "that: rules that force stiffness, that stop it engaging with what the student said, that "
          "make it restate or re-ask, or that conflict with each other so the model must pick one.",
          "The output format demands HIT/PARTIAL/TAUGHT/EVIDENCE/STUCK/ADVANCE before SAY. Find ways "
          "this bookkeeping degrades the SAY text itself — length, tone, naturalness, or the model "
          "narrating its own grading to the student.",
          "Find situations a real interview hits that the contract gives NO guidance for: the "
          "student asks a question instead of answering; disagrees and is right; answers a later "
          "phase early; goes on an interesting tangent; gives a one-word answer; says 'skip this'; "
          "asks to go back; admits they have never seen the topic.",
          "The contract says teach fully when hints are exhausted, but never pre-emptively. Find "
          "cases where those two collide, or where a student gets stonewalled while visibly stuck, "
          "or gets a lecture on something they already showed they understood."]:
    add("role", "app/interview/context.py", f)

# ---- phase machinery: the main source of unnatural flow --------------------------------
for f in ["Phases advance only when core points are hit or none is open. Think about how this FEELS "
          "to a student across a whole session: find flows where the interview lingers on something "
          "exhausted, jumps on before they are ready, or changes topic with no transition.",
          "render_phase shows the model the current phase's points with [DONE]/[OPEN]/[MISSED] "
          "markers and probes. Find ways this makes it read a checklist aloud, telegraph how many "
          "points remain, grade out loud, or refuse to follow the student because no point matches.",
          "Hint tiers release on a counter of stuck signals the MODEL reports. Find cases where the "
          "student is obviously stuck but no signal fires, where a hint arrives after they already "
          "worked it out, or where the tier resets and takes support away mid-struggle.",
          "In a mixed loop the subject changes between segments. Find how that lands on the student: "
          "is the change explained, is context carried, could it switch topic mid-thought, and does "
          "the previous subject's state bleed into grading the next one."]:
    add("flow", "app/interview/session.py", f)

# ---- memory: what a good interviewer would remember ------------------------------------
for f in ["compact_transcript keeps the last few exchanges verbatim, a list of questions already "
          "asked, and a digest of the student's words. Find things a good interviewer WOULD have "
          "remembered that are dropped: a correction, a stated assumption, something they said they "
          "did not know, a promise to come back to something.",
          "The dossier claims to make this better than a fresh chat. Read what it actually renders "
          "and find where it is useless, stale, or actively misleading to the interviewer — for "
          "example weak areas from a topic that is not being asked, or habits inferred from too "
          "little evidence and then stated as fact.",
          "topic_recall tells the interviewer a student has sat this topic before, in counts only. "
          "Find ways this backfires: the interviewer implying it knows their past score, going "
          "easier or harder unfairly, or skipping setup the student actually needed."]:
    add("memory", "app/interview/context.py", f)

# ---- the corpus: rubrics are the questions themselves ----------------------------------
for f in ["Open several rubric JSON files under problems/_interview/rubrics/. Judge them as "
          "INTERVIEW MATERIAL: are the must_hit points things a student could plausibly say out "
          "loud, or are they essay fragments no one would utter? A point that cannot be said is a "
          "point that can never be hit, which is how an interview stalls.",
          "Across several rubrics, find points that overlap or restate each other within a phase or "
          "across phases of the same topic — that is how an interview ends up asking the same thing "
          "twice under two different ids.",
          "Check the phase ORDER in several rubrics. Find topics where the ordering forces an "
          "unnatural conversation: detail before context, tradeoffs before mechanics, or a first "
          "question that is a bad opener.",
          "Read the hints (tier 1/2/3) in several rubrics. Find tiers that give away the whole "
          "answer at tier 1, tiers that are all the same, or a tier 3 that still does not unblock "
          "someone genuinely stuck."]:
    add("corpus", "problems/_interview/rubrics/", f)

# ---- grading: does it reward the right thing -------------------------------------------
for f in ["The model returns point ids; the app scores from them. Find ways a student who genuinely "
          "understands ends up scored badly: correct but differently worded, correct via a valid "
          "alternative approach, correct but terse, or answering two points in one sentence.",
          "phase_score weights core at 2 and others at 1, and counts an unruled point as missed at "
          "close. Find sessions where the resulting number would badly misrepresent the student.",
          "The report shows misses with the student's own words quoted. Find cases where that quote "
          "is misleading, empty, attributed to the wrong point, or embarrassing rather than useful."]:
    add("grading", "app/interview/dossier.py", f)

# ---- the student's actual experience ----------------------------------------------------
for f in ["Read how a turn is displayed and composed. Find things that get in the way of thinking: "
          "losing a half-typed answer, no way to see the question while answering, no way to ask a "
          "clarifying question, no way to end or pause gracefully.",
          "Find ways the interface misrepresents progress or state to the student mid-interview — "
          "the phase rail, the hint indicator, the thinking indicator, the completion panel."]:
    add("client", "app/static/interview.js", f)

# ---- infrastructure: still real, but weighted lightly -----------------------------------
add("infra", "app/interview/jobs.py",
    "Find an interleaving of two workers plus the cloud thread where one turn is answered twice, a "
    "turn is lost, or a good turn is failed too early. A duplicated or lost turn is visible to the "
    "student as a broken conversation.")
add("infra", "app/interview/session.py",
    "resume / delete / start ordering: find a sequence that loses a student's typed answer, "
    "duplicates a turn, or leaves a session that can never continue.")
add("infra", "app/server.py",
    "Find any /api/interview/* route that fails to scope by the logged-in user, so a crafted id "
    "reads or mutates another student's interview.")
add("infra", "app/runner/md.py",
    "This renders UNTRUSTED model output into HTML. Find input producing an unescaped tag or "
    "javascript: URL, or that mangles code/maths a student needs to read.")

# ---- GROUNDED CRITIQUE: real transcripts from real sessions ----------------------------
# The highest-value audit in the fleet. Everything else reasons about what the code MIGHT do to a
# conversation; this reads what it actually did to one. 136 turns across three real sessions.
_TX = ".bughunt/real_transcripts.txt"
for f in ["Read the transcript file end to end and judge it as an interview COACH would. List every "
          "moment where a good human interviewer would have done something different: a question "
          "that should not have been asked, an answer that deserved a follow-up and did not get "
          "one, a explanation given at the wrong moment or wrong depth.",
          "Find every instance in these transcripts where the interviewer repeated itself, "
          "re-asked something already covered, or asked the student to restate something the "
          "interviewer itself had just explained. Quote each one and say what triggered it.",
          "Find every place the interviewer ignored or steamrolled what the student actually wrote "
          "— a question they asked, a confusion they expressed, a correct answer phrased "
          "differently, an interesting point worth following.",
          "Judge the TEACHING in these transcripts. When the student said they were stuck, was the "
          "explanation actually good — right depth, concrete, worth the student's time? Find "
          "explanations that were too shallow, too long, or that did not address the confusion.",
          "Judge the PACING and transitions. Find abrupt topic changes, phase jumps with no bridge, "
          "questions stacked together, or moments where the interview should have wrapped up a "
          "thread and moved on but did not.",
          "The student typed things like 'we already answered this' and 'You're asking the same "
          "question again'. Find EVERY signal of student frustration or disengagement in these "
          "transcripts, and identify what the system did that caused it.",
          "Compare these transcripts against what one plain chat session with the same notes and a "
          "'interview me' system prompt would plausibly have produced. Name the specific places "
          "where this scaffolded system is WORSE, and the places it is genuinely better.",
          "Look at the interviewer's opening turns and its closing turns across the three sessions. "
          "Find weaknesses in how interviews start and end — orientation, expectation setting, "
          "summary, actionable takeaways."]:
    add("transcript", _TX, f)

# ---- corpus, by rubric TYPE: each shape fails differently -------------------------------
for kind, hint in [("HLD system-design", "hq"), ("LLD class-design", "lq"),
                   ("CP competitive-programming", "0"), ("CS-fundamentals notes-derived", "os_")]:
    add("corpus", "problems/_interview/rubrics/",
        f"Sample several {kind} rubrics (ids starting '{hint}'). Judge them as interview material "
        f"for a student: are the must_hit points sayable out loud, is the phase order how a real "
        f"interviewer would run it, do the probes provoke thinking or just quiz, and would a strong "
        f"student plausibly hit every core point in a normal conversation?")

for f in ["Compare a rubric's must_hit points against the SOURCE notes it was generated from, under "
          "problems/_interview/research/. Find points that overstate, misstate, or invent detail "
          "the source does not support — a student graded against a wrong point is worse than no "
          "grading at all.",
          "Find rubrics whose phases have wildly uneven point counts or difficulty, so one phase is "
          "over in a turn and another grinds — that unevenness is what makes an interview feel "
          "arbitrary."]:
    add("corpus", "problems/_interview/", f)

# ---- more angles on flow and helpfulness ------------------------------------------------
for f in ["Trace what happens across a FULL session from opening to report for one topic. Identify "
          "the points in that arc where a student learns the least per minute spent, and why.",
          "The student can say 'I'm stuck'. Trace every code path that word triggers and judge "
          "whether the response a student gets is proportionate to being stuck once, three times, "
          "or persistently on the same point.",
          "Find ways the system treats a student's QUESTION as if it were an ANSWER to be graded — "
          "and what that does to their score, the hint counter, and the flow.",
          "Find what happens when a student gives a correct answer that covers points from a LATER "
          "phase. Is the knowledge credited, ignored, or re-asked later as though unsaid?"]:
    add("flow", "app/interview/session.py", f)

INTERVIEW_PROMPT = """You are going to BE A STUDENT in a mock technical interview, and then say
what was wrong with it.

{contract}

STEP 1 — HOLD THE INTERVIEW. Work in {cwd}. Use this CLI; each command is one real turn through the
production code path, so treat it as a live conversation:

    export OAJ_DB=/tmp/hunt_{tid}.db
    export OAJ_CLI_USER={uid}
    python3 interview_cli.py start {rubric}
    python3 interview_cli.py say <session_id> "your answer here"

YOUR CHARACTER — stay in it for every answer:
{persona}

Do AT LEAST 8 exchanges (more if it is still interesting). Answer as your character genuinely
would — do not try to be a good student unless that is your character. A turn can take up to 30
seconds; that is expected, wait for it.

STEP 2 — LOOK AT WHAT HAPPENED.
    python3 interview_cli.py show <sid>      the full transcript
    python3 interview_cli.py state <sid>     phase, hint tier, which rubric points were credited
    python3 interview_cli.py report <sid>    the report the student would receive

STEP 3 — CRITIQUE IT, HARD. You just sat through this. Where was it worse than a plain chat with a
good model would have been? Consider EVERYTHING: the opening, whether it listened, whether the
questions were good questions, the depth and timing of explanations, transitions, pacing, whether
your answers were graded fairly, whether the report told you anything useful, whether you would
come back tomorrow. Be specific and quote the transcript.

STEP 4 — FIND THE CAUSE. For each thing you disliked, read the code that produced it — the flow
lives in app/interview/session.py and context.py, the wording of the interviewer's instructions is
the ROLE string in context.py, the questions themselves are JSON under problems/_interview/rubrics/.
Name the specific cause where you can.

Do not modify any file.

{output}"""

AUDIT_PROMPT = """You are auditing ONE file of a production mock-interview system for REAL defects.

{contract}

FILE TO AUDIT: {path}

YOUR SPECIFIC FOCUS:
{focus}

RULES:
- Read the file. Read whatever else you need to be sure. Do not modify anything.
- Report ONLY defects you can justify with a concrete trigger: specific inputs, ordering, or state
  that produces the wrong result. If you cannot state the trigger, do not report it.
- Do NOT report: style, naming, type hints, missing docstrings, "consider adding logging",
  broad refactors, or anything the code visibly handles nearby.
- Prefer few real findings over many weak ones. Zero findings is a valid and useful answer.

OUTPUT: a JSON array (and nothing else) of objects with keys:
  "severity"  one of high | medium | low
  "property"  which of P1-P6 it violates, or "other"
  "where"     function name and approximate line
  "trigger"   the exact inputs/ordering that cause it
  "effect"    what goes wrong for the user or the data
  "fix"       one sentence
Return [] if you find nothing real."""


OUTPUT_SPEC = """OUTPUT: end your reply with a JSON array (and nothing after it) of objects with keys:
  "severity"  high | medium | low  — how much it degrades the interview for a student
  "property"  Q1..Q7 (repetition/deafness/rigidity/misgrading/whiplash/unhelpful/amnesia)
              or S1..S3 for the secondary safety ones, or "other"
  "where"     the file+function, or the transcript turn you are quoting
  "trigger"   the exact conversation or state that causes it
  "effect"    what the student experiences, in one concrete sentence
  "fix"       one sentence
Return [] only if you genuinely found nothing worth changing."""


def run(task, timeout):
    if task["mode"] == "interview":
        uid = 91000 + int(task["id"].split("-")[-1])
        p = INTERVIEW_PROMPT.format(contract=CONTRACT, cwd=HERE, tid=task["id"], uid=uid,
                                    rubric=task["rubric"], persona=PERSONAS[task["persona"]],
                                    output=OUTPUT_SPEC)
    else:
        p = AUDIT_PROMPT.format(contract=CONTRACT, path=task["path"], focus=task["focus"])
    t0 = time.time()
    try:
        r = subprocess.run(
            ["cursor-agent", "-p", "--trust", "--mode", "ask", "--model", MODEL, p],
            cwd=HERE, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        out = (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        out = "__TIMEOUT__"
    except Exception as e:
        out = f"__ERROR__ {e}"
    dt = time.time() - t0
    with open(os.path.join(OUT, task["id"] + ".txt"), "w", encoding="utf-8") as fh:
        fh.write(out)
    return task, dt, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=5, help="concurrent agents (RAM-bound)")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--only", default="", help="comma-separated areas")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    tasks = TASKS
    if a.only:
        want = {x.strip() for x in a.only.split(",")}
        tasks = [t for t in tasks if t["area"] in want]
    if a.list:
        for t in tasks:
            print(f"  {t['id']:14} {t['path']:34} {t['focus'][:70]}…")
        print(f"\n{len(tasks)} tasks")
        return 0

    os.makedirs(OUT, exist_ok=True)
    print(f"{len(tasks)} audits, {a.batch} at a time, {a.timeout}s each, model={MODEL}\n")
    done = 0
    with ThreadPoolExecutor(max_workers=a.batch) as pool:
        futs = [pool.submit(run, t, a.timeout) for t in tasks]
        for f in as_completed(futs):
            t, dt, out = f.result()
            done += 1
            n = out.count('"severity"')
            state = "TIMEOUT" if "__TIMEOUT__" in out else f"{n} finding(s)"
            print(f"  [{done}/{len(tasks)}] {t['id']:14} {dt:5.0f}s  {state}", flush=True)
    print(f"\nraw output in {OUT}/ — every finding must be VERIFIED before it is believed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
