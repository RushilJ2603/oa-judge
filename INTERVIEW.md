# Mock interview — how it works and how to run it

An interviewer grounded in **your** notes and research, that remembers you between sessions.

## Why this beats asking Gemini to "be my interviewer"

A chat window is stateless and ungrounded. Four things here are not:

1. **It knows what you already got wrong.** Every rubric point you miss becomes evidence in a skill
   model. A later session can open on your weak areas instead of asking you to re-explain yourself.
2. **It is graded against your material.** Questions and their must-hit points come from your own
   `sd_research` / `cp_research` / notes, so it probes at the depth you actually study.
3. **It cannot flatter you.** Scores are computed by the app from rubric point ids. The model never
   writes a number, so nothing you type can move one.
4. **It cannot leak the answer.** Only the current phase is ever in the prompt, and hint tiers are
   released one at a time by the app. Deeper hints are physically absent until earned.

Measured proof of (3)/(4): bare Gemini Flash, given a one-of-four answer about MVCC with no rubric,
replied *"Your answer is correct."* The same model family, given the rubric, returned
`HIT: 1 / MISSED: 2,3,4` and probed the most important gap.

## Running it (host mode)

The interviewer runs on **your machine**, inside WSL (agy is not available to native Windows).
Starting the worker **is** the host toggle: while it runs, the site shows "Interviewer online" for
you and your friends; stop it and the site says offline and the Fly machine goes back to sleep.

```bash
# one-time: set the same secret on the server and keep it out of git
python3 -c "import secrets; print(secrets.token_urlsafe(32))"     # generate
fly secrets set OAJ_WORKER_TOKEN=<that value> -a oa123            # server side

# every session:
export OAJ_WORKER_TOKEN=<that value>
python3 interview_worker.py                     # add --server http://127.0.0.1:5137 for local
```

Then open the site → **Interview** tab.

### Cost

Polling only happens while the worker runs, and you are using the site anyway during an interview,
so the marginal cost is ~zero. Leaving the worker up 24/7 keeps the Fly machine awake (~$3/mo) —
that is the only way this stops being free. Run it when you want to practise.

## Letting friends use it

Friends sign in with GitHub (restrict with `OAJ_GITHUB_ALLOWED`) and use it while your worker runs.
Their sessions consume **your** Gemini quota, so there are caps: 120 turns/user/day and at most 2
concurrent model calls.

Because their typed answers reach a machine you own, the worker is deliberately defanged:

| Risk | Control |
|---|---|
| Prompt injection reaching an agent with tools | agy runs with **no workspace dirs**, from an empty scratch dir, `--sandbox`, never `--yolo` |
| Injection steering the interview | Answers are delimited and labelled untrusted; the prompt is built server-side from gated rubrics |
| Faking a score | Scores are computed from rubric ids by the app; the model never emits a number |
| A friend reading others' answers | Workers authenticate with `X-Worker-Token`, a separate identity from user login; every query is scoped by `user_id` |
| Draining quota / spawning many agy processes | Per-user daily cap, queue depth limit, max 2 concurrent |
| A browser posting a fake "model response" | Model output is folded into session state server-side only |

## How a session runs

The app picks the question and owns judgement; the model supplies language.

1. **Phases.** HLD walks requirements → estimation → api → data_model → architecture → deep_dives →
   bottlenecks. LLD and CP/concept rounds have their own vocabularies.
2. **Advancement** happens only when every `core` point in a phase is hit — evidence, not opinion.
   A model that claims `ADVANCE: YES` prematurely is overridden.
3. **Hints** escalate after repeated stuck-signals (2 per tier), and reset each phase.
4. **Late credit** counts: open points are only marked missed when the phase actually closes.
5. **The report** lists per-phase scores plus every miss with your own words quoted back.

## Regenerating the rubric corpus

Build-time only — the running site never needs a generator installed.

```bash
python3 extract_rubrics.py                 # resumable; skips anything already passing
python3 gate_rubric.py problems/_interview/rubrics/hq01_url_shortener.json \
        --source problems/_interview/research/sd/hq01_url_shortener.md
```

Every generated rubric must pass `gate_rubric.py`, which enforces exact schema, unique point ids,
per-phase hint tiers, at least one core point — and **rejects any number that does not appear in the
source research file**. That last rule is the important one: an invented-but-plausible figure is the
failure mode most likely to survive human review. Failures retry once, then quarantine; a
quarantined file never reaches the corpus.

```bash
python3 test_interview.py                  # 17 invariants: scoping, hint gating, flat cost, injection
```
