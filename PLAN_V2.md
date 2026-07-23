# OA Judge v2 — Concrete Plan

**Goal:** every attempt and every half-written line stored durably and queryably; a real editor
with autocomplete; a stable server; and a shared question bank where any friend adding a
problem makes it appear for everyone.

**Status:** APPROVED 2026-07-23. Phases 0–6 all in scope.

### Locked decisions
| Decision | Choice | Consequence |
|---|---|---|
| Scope | **Phases 0–6, including hosting** | Phase 6 sandboxing is required work, not optional |
| Editor | **Monaco, vendored locally** | offline; kills the caret/paste bug class; clangd LSP stays Tier 2 |
| Repo layout | **Two repos** (`oa-judge` + `oa-problems`) | problems dir is a separate clone; app reads `PROBLEMS_DIR` |
| Visibility | **Public** | transcribed company OA questions will be publicly searchable — flagged and accepted |

Because hosting is in scope, two things bind earlier than they otherwise would:
- the SQLite schema must stay **strictly Postgres-portable** from day 1 (no SQLite-only types or
  `INSERT OR REPLACE`; use standard SQL + explicit upserts);
- the runner must be refactored behind an **execution-backend interface** in Phase 4 so Phase 6 can
  swap local-subprocess for container-per-run without rewriting the judge.

---

## 0. Where the data actually is today (audited 2026-07-23)

| Data | Stored? | Location | Risk |
|---|---|---|---|
| Attempt metadata | yes | `app/data/history.json` (30 rows) | flat file, no code attached |
| Submitted source code | **NO** | — | permanently lost after each submit |
| Draft / half-written code | browser only | `localStorage["<pid>:<lang>"]` | one slot, overwritten every keystroke |
| Run-with-custom-input | **NO** | — | not recorded |
| OA session duration | **NO** | `duration_s` is `null` on all 30 rows | frontend never sends it |
| Custom stdin you typed | **NO** | — | |
| Notes / "why I got this wrong" | **NO** | — | |
| Reference solutions, editorials, tests | yes | `problems/<id>/` | safe, file-based |

### Two known live problems
1. **Draft loss surface.** All personal code sits in one browser's localStorage, unversioned.
   One "Reset" click or one *Clear browsing data* wipes it.
2. **Stranded drafts from the port move.** localStorage is partitioned by origin
   (scheme + host + **port**). Drafts written while the app served `127.0.0.1:5000` are invisible
   to the app now serving `127.0.0.1:5137`. They still exist in the browser and are recoverable —
   but only until browser data is cleared.

---

## 1. Architecture decision (the one that shapes everything else)

**Personal data → local SQLite. Problems → git. Execution → always local.**

```
     ┌──────────────────────────────┐
     │  oa-problems  (GitHub repo)  │   shared question bank, one dir per problem
     └──────────────┬───────────────┘
            git pull │ git push (PR)
     ┌──────────────▼───────────────┐
 you │  oa-judge (app, local)       │  friends run their own identical copy
     │  ├─ problems/   ← the repo   │
     │  ├─ app/data/judge.db  ← YOUR sqlite, gitignored, never shared
     │  └─ compile + run happen HERE, on your machine
     └──────────────────────────────┘
```

**Why this split, stated plainly:**

- *Problems in git, not in a DB.* A problem is a folder of text files. Git already gives you
  versioning, review, conflict-free merges (each problem is its own directory, so two people
  adding problems never collide), and free hosting. A DB would throw all of that away and add a
  server you must keep alive. The DB indexes problems for fast search; **files remain the source
  of truth.**
- *Execution stays local.* This is the important one. The moment a shared server compiles and runs
  code your friends wrote, you own an arbitrary-code-execution service and need real container
  sandboxing (see Phase 6). Keeping execution local makes the shared bank essentially risk-free
  and costs ₹0/month.
- *Personal data local and gitignored.* Your drafts and attempts never enter the repo, so they
  never conflict and are never accidentally published.

Result: sharing works, costs nothing, needs no auth, and works offline.

---

## 2. Database schema (SQLite, written Postgres-portable)

`app/data/judge.db`, WAL mode, plain SQL (no ORM), stdlib `sqlite3` — zero new dependencies.

```sql
schema_version(version INT)                         -- numbered migrations, never lose data

problem_index(                                      -- CACHE of disk; rebuilt on sync
  id TEXT PK, title, difficulty, tags_json, company, source_url,
  runnable INT, languages_json, checksum, indexed_at)

attempt(                                            -- one row per SUBMIT
  id PK, problem_id, language, mode,                -- mode = 'lc' | 'oa'
  verdict, passed, total, duration_s,
  source_code TEXT,                                 -- ← THE CODE. the whole point.
  compile_output TEXT, first_fail_idx INT,
  stdout_snippet, stderr_snippet, runtime_ms, created_at)

run(                                                -- one row per RUN (custom input)
  id PK, problem_id, language, source_code,
  stdin TEXT, stdout, stderr, exit_code, signal, runtime_ms, created_at)

draft(                                              -- live autosave, replaces localStorage
  problem_id, language, source_code, cursor_pos, updated_at,
  PRIMARY KEY(problem_id, language))

draft_snapshot(                                     -- time-travel through half-written code
  id PK, problem_id, language, source_code, created_at, reason)
                                                    -- reason: 'periodic'|'pre-submit'|'pre-reset'

oa_session(id PK, problem_id, started_at, ended_at, duration_s, result, abandoned INT)

note(problem_id PK, body_md, updated_at)            -- your own writeup per problem
flag(problem_id PK, starred INT, revisit INT, confidence INT, last_seen_at)
setting(key PK, value)                              -- theme, handle, editor prefs
```

**Retention:** `run` rows pruned to the last 200 per problem; `draft_snapshot` keeps every snapshot
for 30 days, then thins to one per day. Both configurable, both off by default at this data scale.

**Every write is a transaction; DB opened WAL** — no half-written files, no corruption on crash.

---

## 3. Phases

Each phase leaves the app fully working. Nothing is a big-bang rewrite.

---

### Phase 0 — Safety net *(do first, ~30 min, zero risk)*

1. `cp -r oa-judge oa-judge-backup-2026-07-23` — full snapshot before anything.
2. **Rescue stranded drafts.** Temporarily serve on port 5000, load a one-page
   `/rescue` view that dumps every `localStorage` key to JSON and POSTs it to disk.
   Repeat on 5137. Merge both into `app/data/rescued_drafts.json`.
3. `git init` + `.gitignore` (`app/data/`, `__pycache__`, `*.db`, build temp) + first commit.
   The project currently has **no version control at all** — this is the single largest
   stability risk on the board.

**Exit test:** backup exists; `rescued_drafts.json` contains your real code; `git log` shows one commit.

---

### Phase 1 — Persistence layer

- `app/db.py`: connection, WAL, migration runner, `migrations/001_init.sql`.
- Rewrite `app/runner/history.py` → `app/store.py` against SQLite.
- **Import** existing `history.json` (all 30 rows preserved) + `rescued_drafts.json`.
- `/api/submit` and `/api/run` now persist **full source code** plus outputs.
- New endpoints: `PUT /api/draft`, `GET /api/draft`, `GET /api/attempts/<pid>`,
  `GET /api/attempt/<id>`, `GET /api/stats`.
- Frontend: server-side autosave, debounced 1.5s; localStorage demoted to an offline fallback.
- Fix `duration_s` — frontend actually sends OA elapsed time; `oa_session` rows written.

**Exit test:** submit → kill server → restart → the exact code you submitted is retrievable from
the DB and shown in the UI. Delete browser data → drafts survive.

---

### Phase 2 — Real editor (Monaco) + autocomplete

Replace the hand-written textarea+overlay highlighter with **Monaco** (the VS Code editor),
**vendored locally** into `app/static/vendor/monaco/` — no CDN, still fully offline.

This deletes the entire class of bugs that has cost the most time on this project (caret
misalignment, paste drift, line-height rounding) because Monaco owns the caret and the
highlighting in one layer, by construction.

What you get immediately: correct C++/Python highlighting, bracket auto-close, real auto-indent,
multi-cursor, find & replace, column select, proper undo, minimap, fold.

**Autocomplete, in two tiers:**
- *Tier 1 (this phase):* word-based completion + a curated dictionary — STL containers and
  `<algorithm>` functions, common headers, Python builtins — plus competitive-programming
  snippets (`fori`, `vec`, `fastio`, `sortv`, `pq`, `binsearch`). Zero external processes.
  This is ~90% of the day-to-day value.
- *Tier 2 (optional, later):* a **clangd / pyright LSP bridge** over WebSocket for true semantic
  completion (member completion on your own types), go-to-definition, and inline error squiggles
  before you even compile. Needs `clangd` installed; adds real moving parts. Deferred on purpose.

**Exit test:** paste a 200-line file, scroll to the bottom, edit mid-line — caret and text agree.
Type `vec` + Tab → snippet expands. Type `std::` → completion list appears.

---

### Phase 3 — The data actually becomes useful

The point of storing everything is being able to look at it.

- **Attempt timeline** per problem: every submit, verdict, timestamp, and the code — click any row
  to view it, **diff any two attempts** side by side (see exactly what fixed the WA).
- **Draft scrubber**: a slider over `draft_snapshot` to replay how a solution evolved.
- **Stats dashboard**: solve rate, first-attempt-AC rate, attempts-to-AC, verdict mix,
  breakdown by company/tag/difficulty, OA-mode time distribution vs the limit.
- **Notes** panel per problem (markdown, autosaved) + star / "revisit" flags / confidence rating.
- **Global search** across your own code: "where did I write a Fenwick tree before?"
- **Export**: one button → `judge-export-<date>.zip` (DB + all your code as plain `.cpp`/`.py`
  files in a readable tree). Your data is never locked inside this app.

**Exit test:** open millennium-q1, see all 8 real attempts, diff attempt 4 vs 7, read the change.

---

### Phase 4 — Stability

Concrete fixes, each addressing something already observed or clearly latent:

| Fix | Why |
|---|---|
| Serve via **waitress** instead of the Flask dev server | dev server is explicitly not for real use; single-threaded stalls under a stress run |
| Kill the whole **process group** on timeout | a TLE'd C++ program that forked leaves orphans burning CPU today |
| Per-run temp dir + guaranteed cleanup | compile artifacts currently accumulate |
| **Single-instance guard** in the launcher (health-check the port first) | double-clicking the icon twice = port conflict + confusing crash |
| Structured, rotating logs → `app/data/logs/` | "Failed to fetch" gave zero diagnostic signal last session |
| Frontend error toasts + retry on transient failure | same |
| Clear UI message if `g++` is missing | currently surfaces as a 500 |
| **pytest suite** for sandbox/judge/API/store + a `make check` gate | there are currently zero automated tests of the runner |
| Version + health endpoint `/api/health` | lets the launcher and friends verify a good install |

**Exit test:** `pytest` green; TLE leaves no stray processes; launching twice is handled cleanly.

---

### Phase 5 — Sharing (the friend-group bank)

**Repo layout — two repos:**
- `oa-judge` — the application. Friends `git pull` to get app updates.
- `oa-problems` — the question bank, cloned into `oa-judge/problems/`.
  App reads `PROBLEMS_DIR` from config so the two update independently and never conflict.

**In-app, no terminal required:**
- **Sync** button → `git pull` in the problems dir → re-index → *"3 new problems: …"*.
- **Add Problem** form → statement (markdown, live preview), constraints, samples, reference
  solution, generator → writes a valid package to disk → **runs the verifier on it immediately**
  (reference must AC its own tests, stub must fail) → only a green package can be published.
- **Publish** → commit + push a branch, print the PR link (or push straight to `main` if you
  four just trust each other — configurable).

**Trust, so the shared bank stays correct:**
- A **GitHub Action** on `oa-problems` runs `verify_all.py` on every PR. A problem whose reference
  doesn't pass its own tests cannot land. This is what stops the bank rotting as it grows.
- `problem.json` gains `author` and `added_at`.

**Onboarding a friend** must be one command:
```
git clone <oa-judge> && cd oa-judge && ./setup.sh     # clones problems, checks g++/python, first run
```
`setup.sh` verifies g++, Python, Flask, initializes the DB, and prints the URL.

Also folded in here: make **cisco-q1** and **cisco-q2** runnable (still the outstanding
deferred task — specs already in `_migrated_raw/cisco/coding.md`).

**Exit test:** you add a problem in the UI → push → your friend hits Sync → it appears and is
solvable on their machine, with no manual file copying.

---

### Phase 6 — Hosting *(optional, deliberately last)*

Only if you want friends to use it **without installing anything**. Be clear-eyed about the cost:

- Docker image, Fly.io / Railway / a small VPS (~$5/mo), Postgres (schema is already portable) or
  SQLite on a persistent volume, GitHub OAuth for login (you all already have GitHub).
- **The hard part is untrusted code execution.** Each submission must run in a locked-down
  container: `--network none`, read-only filesystem, non-root, seccomp profile, memory/PID/CPU
  caps, ephemeral, hard wall-clock kill. Getting this wrong means a friend's C++ (or a mistake)
  can read your server. This is not a weekend detail — it's roughly the same size as Phases 1–3
  combined.

**Recommendation: don't build this yet.** Phase 5 already gives you the actual goal — everyone
gets every question — with no server, no cost, and no attack surface. Revisit hosting once the
local version has been used enough to prove it's worth the ops burden.

---

## 4. Effort estimate

| Phase | Scope | Rough size |
|---|---|---|
| 0 — Safety net | backup, draft rescue, git init | small |
| 1 — SQLite persistence | schema, migrations, import, API, autosave | medium |
| 2 — Monaco + autocomplete | vendor, integrate, snippets, dictionary | medium |
| 3 — Data UI | timeline, diff, scrubber, stats, notes, export | medium-large |
| 4 — Stability | waitress, proc groups, logs, pytest, launcher | medium |
| 5 — Sharing | repo split, sync/publish, authoring UI, CI, setup.sh, CISCO | medium-large |
| 6 — Hosting | Docker sandbox, Postgres, OAuth, deploy | large (optional) |

Phases 0→1→2 are the ones that directly answer *"is my data safe and is this pleasant to use"*.
If time is short, those three alone are a complete, satisfying upgrade.

---

## 5. Open decisions for you

1. **Scope now** — all of 0–5, or stop after 0–2 (data safety + good editor) and revisit?
2. **Editor** — Monaco (recommended: kills the bug class, real autocomplete) vs. keep the
   hand-written one and only bolt autocomplete onto it?
3. **Repo layout** — two repos (app + problems, recommended) vs. one repo containing both?
4. **Hosting** — confirm deferring Phase 6, or is "friends use it with zero install" a hard
   requirement now?
5. **GitHub** — `gh` CLI is **not installed**; public or private repos? (Private + collaborators
   is free and fine for a friend group.)
