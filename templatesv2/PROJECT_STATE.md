# PROJECT_STATE.md
# ── Living State Document — Update Every Session ────────────────
# Last Updated: 2026-07-24 20:45 IST (session 3 — deploy + scraping pipeline + verified batches) | By: Claude (Opus 4.8, via Claude Code)

## Current Phase
**Live, multi-user, and being filled with content.** All v2 phases (0–6) are done *and deployed*:
the judge runs hosted on Fly.io with GitHub-OAuth multi-user, and there is now a separate scraping
pipeline feeding a growing, verified problem bank. Focus has shifted from *building the judge* to
*populating it with verified OA problems in reviewed batches*.

## What is live right now
- **Hosted:** `https://oa123.fly.dev` (Fly app `oa123`, single `shared-cpu-1x` machine, **scale-to-zero**
  → ~$0/month). GitHub OAuth: everyone signs in and sees only their own attempts/drafts/stats. The
  DB and the problem bank both live on the persistent volume at `/data`. Health: `version:2`,
  **42 problems** (hosted is currently in sync with the bank).
- **Two public repos:** `RushilJ2603/oa-judge` (app) + `RushilJ2603/oa-problems` (bank, cloned into
  `problems/`). Push a problem → anyone clicks **Sync** → it appears for everyone.
- **Bank: 42 packages** — by source: **Iris — Personal (`gyan`) 22**, **TUF+ (`tuf`) 13**,
  **OA-Helper (`oa-helper`) 7**. 40 runnable, 2 statement-only. Sidebar groups by **source ▸ company**.
- **Scraper (sibling project `/mnt/c/Users/jishu/Desktop/oa-scraper`, git-init'd this session):**
  built by orchestrating Grok 4.5 via `cursor-agent`. **TUF+: 397 scraped** (premium fields via the
  authenticated `backend-go.takeuforward.org` API). **OA-Helper: ~1500/3586 scraped** and climbing
  (premium content via the `oahelper.in /api/proxy/question` proxy + `oa_session` cookie). Raw JSON
  is **local + gitignored**; it does NOT go to the app automatically — it is ingested in reviewed
  batches. Resumable (skips existing).

## Shipped this session (session 3, 2026-07-24)
- **Deployed to Fly.io with GitHub OAuth** (multi-user, scale-to-zero, persistent volume). Docker
  per-run sandbox validated live earlier; hosted runs the `local` backend inside the Firecracker VM.
- **Scalable UI:** a `problem_index` search table (rebuilt on startup + after Sync) powers a paginated,
  filtered sidebar; **two-level `source ▸ company` dropdown** (TUF+ / OA-Helper / Iris — Personal),
  company filter + search. Relabelled the legacy `gyan` source to **"Iris — Personal"** (key unchanged
  on disk). Presence chip: **best-effort "who's online", $0** (last_seen bumped by real traffic, no
  heartbeat; migration `004_presence.sql`, `/api/presence`).
- **Sync-persistence fix:** the live bank now lives on the **persistent volume** (`OAJ_PROBLEMS_DIR=
  /data/problems`), seeded once from the image-baked `/problems` via `sharing.ensure_seeded()`.
  Previously the bank sat in the container's ephemeral fs, so scale-to-zero discarded every `git pull`
  on cold start — the "have to click Sync several times" bug. Now one Sync sticks.
- **Stub-rule regression fixed + gated:** all stubs now expose a **separate solution function** (never
  solve inside `main()`). New `audit.py` structural gate hard-fails that (plus missing metadata /
  reference / sample), and **enforces test quality** (warns below 5 edge cases). `SOLUTION.md` is the
  new authoritative "what we built + how we author" reference. **`FORMAT.md` in the bank** now points
  to both gates and states the mandatory test standard.
- **Verified problem batches ingested** (each: stub-with-separate-function, verified reference,
  ≥5 edges incl. max-scale/overflow, `verify_all` + `audit` green, **independent brute-force
  cross-check**):
  - **Microsoft — TUF+ textbook (13):** 3 Easy (assign-cookies, best-time-to-buy-and-sell-stock,
    climbing-stairs) + 10 Med/Hard (best-time-ii, count-inversions, aggressive-cows, book-allocation,
    binary-subarrays-with-sum, xor-k, nice-subarrays, candy, 0/1-knapsack, burst-balloons).
  - **Microsoft — OA-Helper story (2):** Calculate Amount (prefix-min), Final Price (monotonic stack).
  - **Goldman — Iris-Personal (3):** Missed Courses, Unstable Tasks, Largest Container (union-find;
    reading validated against full BFS reachability).

## Blocking Issues
- **NONE** for the app or the deployment.

## Next Session Must Start With
> **User's direction on content** — the judge and pipeline are done; remaining work is populating the
> bank in reviewed batches. Options, all "just say which":
> 1. **More Microsoft** (243 TUF textbook remain; more OA-Helper story problems — verify each, skip
>    the sample-less / self-contradicting ones like #8 Square Tile Arrangement).
> 2. **Finish the OA-Helper scrape** (~2000 left of 3586; the `oa_session` cookie expires — re-capture
>    from oahelper.in DevTools → Cookies if 401s appear).
> 3. **Backfill the 14 older problems** flagged by `audit.py` for having <5 edge cases.
> Every batch goes through the same gate: verified reference + brute-force cross-check + ≥5 edges +
> `verify_all` + `audit`, then push to `oa-problems`; the user Syncs.

## Environment Notes
- OS: Windows 11 + WSL2; app at `C:\Users\jishu\Desktop\oa-judge` (= `/mnt/c/Users/jishu/Desktop/oa-judge`).
- Scraper: `/mnt/c/Users/jishu/Desktop/oa-scraper` (own `.venv`; httpx/bs4/markdownify; `config.local.json`
  holds the TUF Bearer token + OA-Helper `oa_session` cookie — **gitignored, never commit secrets**).
- `cursor-agent` (Cursor CLI) installed at `~/.local/bin`, logged in; used to drive Grok 4.5 scoped to
  the scraper repo only (never the app). Verify its output; never trust its self-report.
- Python 3.12, `g++` 13.3 (C++17). Server binds `127.0.0.1:5137` locally; hosted binds `0.0.0.0:5137`.
- Fly CLI (`flyctl`) at `~/.fly/bin`, authenticated.

## Recent Decisions (this session)
| Decision | Rationale | Date |
|---|---|---|
| Live problem bank lives on the Fly **persistent volume** (`/data/problems`), seeded from the image | Scale-to-zero wipes the ephemeral fs; a baked-only bank reverts each cold start and Syncs don't stick | 2026-07-24 |
| Stub `main()` only does I/O and calls a **named solution function**; enforced by `audit.py` | A batch regressed to solving inside `main()`; mirrors real OA/LC harness; now a hard gate | 2026-07-24 |
| **Test quality mandatory**: ≥5 curated edges incl. a max-scale case; brute-force cross-check every reference | Weak suites let a wrong/slow solution pass; audit warns below 5 | 2026-07-24 |
| Presence is **best-effort, no heartbeat** (last_seen on real traffic only) | A background heartbeat would keep the scale-to-zero machine awake and cost money | 2026-07-24 |
| Delegate the **scraper only** to Grok (`cursor-agent`), scoped to `oa-scraper`; author judged packages myself | Bulk scraping fits delegation; authoring/verification stays with Claude; app never touched | 2026-07-24 |
| Skip OA problems whose provided solution contradicts their own samples (e.g. #8 Square Tile) | Can't ship a guessed judge; verification discipline over coverage | 2026-07-24 |

## Known Issues / Tech Debt
- **OA-Helper scrape is partial** (~1500/3586) and the `oa_session` cookie expires — resume with a
  fresh cookie when needed. Raw only; not yet ingested.
- **14 older problems have <5 edge cases** (audit warnings) — deshaw-q1, flipkart-q4, goldman-2048,
  goldman-book-cricket, goldman-dora, goldman-non-repeating, millennium-q2, oa-q1/q2/q3,
  rippling-q1/q2, uber-q3, tuf-climbing-stairs — backfill to the new standard when convenient.
- **Two problems deferred (correctly)**: Array Burst (removal order not confluent), Optimal
  Reconstruction (unreadable sample tree edges) — need clarification before a judge can be written.
- Many premium OA-Helper questions have **no stored sample tests** in the API → only author the ones
  with clear semantics + samples that can be verified.
- The templates' own `CLAUDE.md`/dead_ends still carry some **v1 history** (the pre-Monaco overlay
  editor) — kept as history; the live editor is Monaco.

## Reference Links
- `SOLUTION.md` (authoritative: architecture + authoring rules), `problems/FORMAT.md` (package format +
  test standard), `API.md`, `PLAN_V2.md`/`DEPLOY.md`. Gates: `verify_all.py` (correctness), `audit.py`
  (structure + test-quality).
- Hosted: `https://oa123.fly.dev`. Repos: `github.com/RushilJ2603/oa-judge`, `.../oa-problems`.
