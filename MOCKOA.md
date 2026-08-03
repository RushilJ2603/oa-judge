# Mock OA — timed papers

A **paper**: two to four questions, one clock, one score. The judge could already time a single
problem (`oa_session`), and that is a different exercise. What a real OA measures, and what solving
one problem at a time cannot, is **triage** — which question you open first, when you cut your
losses on Q2, whether you left enough of the clock for the hard one.

Tab: **Mock OA**. Fifteen hand-picked papers (five each at 1, 2 and 3 hours), or build a random one
at any offered length.

---

## The rules the feature is built on

**1. The clock belongs to the server.** `ends_at` is written once, at start, and never touched
again. The countdown in the browser is a *rendering* of it, re-synced every 60 seconds and on tab
focus. Reloading, closing the laptop, or opening a second device cannot buy a minute, and a paper
that runs out while the tab is closed is closed **server-side** at the right moment with the right
score.

**2. A submission counts only inside the window.** Scoring reads `attempt` rows between
`started_at` and the deadline — so an AC twenty minutes late is practice, not a result. Solving a
question yesterday scores nothing today.

**3. Results are derived, never stored twice.** Per-question outcomes come from the same `attempt`
rows the rest of the app uses, so a paper can never disagree with your history or your solved
badges. Only the final snapshot is frozen (`score_json`) so an old report stays readable.

**4. Nothing names the technique.** Cards carry title, difficulty and company — no tags, no topic.
This is the rule the problem list already follows (it hides `topic` deliberately) and it matters
most here. Hand-written blurbs may describe pacing, ramp and traps; naming an algorithm is a test
failure, not a style preference (`test_mockoa.py` greps for it). The two **themed drills** are the
disclosed exception — their family is in the title on purpose.

**5. Partial credit is real.** A submission that clears 8 of 10 hidden tests scores 80 on that
question. Reporting it as a plain fail hides the near-misses, which are the most useful line in a
report.

---

## The time model (random papers only)

| Difficulty | Expected solve time |
|---|---|
| Easy | 18 min |
| Medium | 32 min |
| Hard | 50 min |

A random paper is any **non-decreasing** ladder of 2–4 questions whose estimates sum to between
78% and 114% of the requested length. That is what "adjust the number of questions to the
difficulty" means in practice: three hours is four questions when two of them are Hard, and can be
three when all are. Longer ladders are weighted higher (a paper of 2 questions in 3 hours is legal
but unlikely), questions you have never solved are preferred, and each slot tries for a different
technique family so one weakness cannot fail the whole paper.

The budget deliberately runs under the paper length — a paper budgeted to exactly 100% is a paper
nobody finishes, because reading, debugging and resubmitting are not in the estimate.

The **curated papers ignore this model**: their length is hand-set. Amazon's intern paper really is
two mediums in an hour.

---

## Adding or editing a paper

Papers live in `app/mockoa_sets.json`. Add an object to `sets`:

```json
{
  "id": "kebab-case-unique",
  "title": "Company — Paper name",
  "company": "Company",
  "minutes": 120,
  "blurb": "Pacing advice. No algorithm names.",
  "problems": ["problem-id-1", "problem-id-2", "problem-id-3"]
}
```

Then run `python3 test_mockoa.py`. It fails if a problem id does not exist, is not runnable, is
already used in another paper, if the ramp goes backwards, if the paper is over-stuffed for its
length, or if the blurb names a technique. No restart is needed in dev — the file is re-read when
its mtime changes.

---

## Behaviour inside the judge

Opening a question from the bar switches to the judge and forces **OA mode** (hidden tests), which
is the point of an OA. Its *one-submission* lock is skipped while a paper is running: that lock is
a practice rule for solving a single problem under self-imposed pressure, and real OA platforms let
you resubmit until the clock stops. The clock is already the constraint.

The running bar sits above the workspace, outside every view, because you sit the paper in the
judge — a status bar you have to navigate away from your code to read is not a status bar.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mock-oa` | catalogue + history + the running paper |
| POST | `/api/mock-oa/random` | compose a paper without starting it (`{minutes}`) |
| POST | `/api/mock-oa/start` | `{set_id}` or `{minutes, problems[]}` |
| GET | `/api/mock-oa/active` | running paper, live per-question state, seconds left; closes an expired one |
| POST | `/api/mock-oa/finish` | hand in early; idempotent |
| GET | `/api/mock-oa/attempt/<id>` | a past paper's report |
| DELETE | `/api/mock-oa/attempt/<id>` | delete a past paper |

Starting a paper while one is running **abandons** the first: two live clocks would both claim the
same submissions, and you can only sit one OA at a time.
