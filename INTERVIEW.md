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

**Double-click `Start Interviewer` on the Desktop.** While that window is open the site shows
"Interviewer online" for you and your friends; close it and the site goes offline and the Fly
machine sleeps again.

It bridges Windows → WSL (agy is not available to native Windows) and reads the token from `.env`,
which is gitignored. Equivalent by hand:

```bash
cd /mnt/c/Users/jishu/Desktop/oa-judge
set -a && . ./.env && set +a
python3 interview_worker.py                     # add --server http://127.0.0.1:5137 for local
```

Then open the site → **Interview** tab.

## Response time

Measured on the agy CLI path: **~16s per turn**, of which 14–16s is the model itself.

The CLI is the floor. Breaking it down: 0.3s process start + ~5s auth handshake + ~8s generation,
with no warm-up across calls and no usable token streaming (agy parses `--output-format stream-json`
as prompt text). Model tier barely moves it — a two-token reply still takes ~14s.

What *was* removable, and is:

| Cause | Fix | Saved |
|---|---|---|
| Worker's fixed 20s idle poll — after you hit send it could sit that long before leasing your turn | adaptive backoff: fast while a session is live, easing off when truly idle | **~20s** |
| Plugin wrapper around agy | call `agy` directly | ~1.5s |
| Browser poll granularity | 2s → 1s | ~1s |

Net: **36s → 16.1s per turn.**

**Set `GEMINI_API_KEY` to go much faster.** The worker then uses the Gemini HTTP API (~1–3s per
turn) instead of the CLI, skipping the per-call handshake entirely. Nothing else changes — same
rubrics, same memory, same scoring. Unset, it falls back to agy.

## Capacity

Verified with `loadtest_interview.py`, which simulates N users plus a worker and asserts no
duplicated turns, no job leased twice, and no cross-user leakage.

- **16 users × 2 turns: 0 errors, 0 double-leases.**
- Worker concurrency is the throughput knob (`OAJ_INTERVIEW_CONCURRENCY`, default 6; production
  runs 12). Turns are network-bound, so concurrency scales past core count.
- At concurrency 12, 16 simultaneous users see median ≈ the model floor rather than queueing.
- Caps that protect the shared subscription: 120 turns/user/day, queue depth 200.

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
