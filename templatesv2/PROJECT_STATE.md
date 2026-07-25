# PROJECT_STATE.md
# ── Living State Document — Update Every Session ────────────────
# Last Updated: 2026-07-25 22:35 IST (session 4 — mutation-testing gate, gated Grok pilot, app features, $0 storage) | By: Claude (Opus 4.8, via Claude Code)

## Current Phase
**Live, multi-user, and scaling content behind an enforced quality gate.** The judge is hosted on
Fly.io with GitHub-OAuth multi-user. This session turned quality from a checklist into *tooling*:
a mutation-testing gate now certifies test-suite STRENGTH, and Grok may bulk-author problems because
nothing merges without `gate_candidate.py` = PASS. Focus is populating the bank at scale, safely.

## What is live right now
- **Hosted:** `https://oa123.fly.dev` (Fly app `oa123`, **release v10**, single `shared-cpu-1x:512MB`,
  **scale-to-zero** → ~$0/mo). GitHub OAuth. DB + bank on the persistent volume at `/data`. Storage/IP
  cost = $0 (1GB volume < 3GB free; shared IPv4 free; dedicated IP is v6 = free). The only Fly charge
  is active compute (~$0.01/hr while serving); a $0.05 line = a few active hours, not waste.
- **Two public repos:** `RushilJ2603/oa-judge` (app, HEAD `48444db`) + `RushilJ2603/oa-problems`
  (bank, cloned into `problems/`, HEAD `05266ce`). Push a problem → anyone clicks **Sync** → it appears.
- **Bank: 62 packages** — by source: **Iris — Personal (`gyan`) 22**, **TUF+ (`tuf`) 13**,
  **OA-Helper (`oa-helper`) 27**. All runnable carry **cpp + py**. Sidebar groups by **source ▸ company**.
  **Bank size 58M** (hidden tests gzipped; was 112M). Live app shows the new problems after a Sync.
- **Four gates** (author identity is irrelevant to all of them):
  `verify_all.py` (reference is correct) · `audit.py` (structure + ≥5 edges) ·
  **`mutation_test.py` (test STRENGTH — 100% killed mutants)** · **`gate_candidate.py`** (one command:
  anchor + independent brute + audit + 100% mutation; a Python-only reference is a hard FAIL).

## Shipped this session (session 4, 2026-07-25)
- **Mutation-testing quality system.** `mutation_test.py` mutates the verified reference (flip
  `<`/`<=`/`==`/`+`/`min`, delete statements) and requires the suite to KILL every non-equivalent
  mutant; survivors are auto-triaged (generator + ±1 fuzz) into equivalent vs a real GAP, and `--fix`
  persists each gap's distinguishing input as an edge test. `gate_candidate.py` composes every gate
  into one PASS/FAIL. Codified in `SOLUTION.md` §4.1–4.2.
- **Four gate-soundness bugs fixed** (see dead_ends): timeout/hang flap, count-field fuzz phantom-gaps,
  reference-crash phantom-gaps, and mutation silently skipped for Python refs.
- **Healed the whole bank to 100% mutation** (goldman-2048, rippling-q2, tuf-aggressive-cows,
  tuf-nice-subarrays), **relabelled 2 mislabeled Easy** (oahelper calculate-amount + final-price,
  were Medium), and **clarified book-allocation** (contiguity + a discriminating 2nd sample).
- **Gated Grok pilot** (`cursor-grok-4.5-high`, 4 agents in isolated `../oa-staging`): **14 problems
  merged** (greedy/heap, segment tree, graph connectivity, bitmask/interval DP, DAG, MEX, digit-DP,
  union-find…), **1 deferred** (valid-number-partitions — Python bignum ref, un-gateable), **3 correct
  SKIPs** (too easy). Also added OA-Helper batches A/B earlier this session (DE Shaw ×2, Arcesium,
  Google, Uber ×2) and enabled **Python as a second language** on all runnable problems.
- **App features (deployed).** (1) **LaTeX rendering** — statements keep `\(…\)`; the renderer converts
  to Unicode + `<sup>/<sub>` (no KaTeX). (2) **One-click bug reporting** — a Report button in the tab
  bar + a box under the statement → `POST /api/report` → `bug_report` table; owner review at
  `/api/reports`. (3) **Topic search** — free-text now matches topic, but topic is HIDDEN on the
  problem view (approach-giveaway).
- **$0 storage.** Hidden tests are gzipped (`*.in.gz`); the judge + `mutation_test` read plain-or-`.gz`
  transparently. **Bank 112M → 58M (2.9×)** — roughly doubles the free-3GB-volume ceiling.
- **Deployed 3×**: Fly **v8** (render + report), **v9** (report button + topic search), **v10** (`.gz`
  reader — shipped BEFORE the compressed bank so the live app can read it).

## Blocking Issues
- **NONE** for the app or the deployment.

## Next Session Must Start With
> **User's direction**, all optional / "just say which":
> 1. **Scale Grok authoring** beyond the pilot (up to 25 agents), each package gated by
>    `gate_candidate.py` in isolated staging — pull more graphs/DP/greedy **medium+hard** from
>    TUF+/OA-Helper (skip easy-mislabeled ones).
> 2. **Ship valid-number-partitions**: convert to a **mod-1e9+7 C++ reference** (re-anchor) or add
>    **Python mutation support** to the gate. Staging copy kept in `../oa-staging/agentD/out/`.
> 3. If the bank must grow well past **~3,500 problems**, **cap max-scale hidden-test size** in
>    `make_hidden` (lossy — trades some TLE coverage; gzip alone is only ~2.9×).

## Environment Notes
- OS: Windows 11 + WSL2; app at `C:\Users\jishu\Desktop\oa-judge` (= `/mnt/c/Users/jishu/Desktop/oa-judge`).
- **Gate tools run heavy** (bits/stdc++.h compiles). Never run two mutation processes at once — that
  OOM-crashed the 10GB WSL VM (the "crash", **not** Grok). Cap with `OAJ_MUT_WORKERS` (default min(4,ncpu)).
  Stage/compile in `/tmp` (ext4); `/mnt/c` (9p) is slow. `OAJ_PROBLEMS_DIR` scopes tools to a candidate.
- Grok pilot staging: `/mnt/c/Users/jishu/Desktop/oa-staging` (agentA..D; gate tools + `scraped/` + `out/`).
  `cursor-agent` authed as jishu373@gmail.com; verify FILES in `out/`, never its self-report.
- Python 3.12, `g++` 13.3 (C++17). Fly CLI (`flyctl`) at `~/.fly/bin`, authed. **`fly deploy` runs
  from the app dir with `-a oa123`.** App code needs a deploy; bank/problem changes only need Sync.

## Recent Decisions (this session)
| Decision | Rationale | Date |
|---|---|---|
| Test-suite strength enforced by **mutation testing**; ship only at 100% killed (non-equivalent) mutants | A bugged solution once passed 17/18 tests; verify_all/audit can't see a weak suite | 2026-07-25 |
| **Grok may bulk-author** OA-judge questions, gated by `gate_candidate.py` in isolated staging | Author identity is irrelevant to the gate; quality is tooling-enforced. DSA-notes prose stays Claude-only | 2026-07-25 |
| A mutant **timeout/crash = KILL** (reliable oracle first); adaptive per-mutant timeout | Skipping timeouts hung the gate; a load blip as data flapped the score | 2026-07-25 |
| Fuzzer perturbs **payload rows only**; `run()` non-zero exit = unreliable | Mangling a count field / crashing the ref fabricates phantom gaps | 2026-07-25 |
| A **Python-only reference is a hard FAIL** (mutation mutates C++ only) | A skipped mutation step must never read as PASS | 2026-07-25 |
| Statements keep **LaTeX**; the renderer converts it (no KaTeX) | Fix the renderer once vs sanitize every problem; stays offline | 2026-07-25 |
| **Topic searchable but hidden** on the problem view | Seeing the topic gives away the approach | 2026-07-25 |
| Hidden tests **gzipped**; deploy the `.gz` reader **before** the compressed bank | ~2.9× smaller ≈ doubles the volume ceiling; ordering keeps the live app readable | 2026-07-25 |

## Known Issues / Tech Debt
- **valid-number-partitions DEFERRED** — Python bignum reference; `mutation_test` mutates C++ only, so
  its suite strength can't be certified. Fix: mod-1e9+7 C++ ref, or Python mutation support.
- **gzip is only ~2.3–2.9×** on max-scale numeric data (high entropy). Past ~3,500 problems, cap
  max-scale hidden-test size in `make_hidden` (lossy) rather than compress harder.
- **OA-Helper scrape is partial** (~1500/3586, raw + local in `../oa-scraper`); the `oa_session` cookie
  expires — re-capture when resuming.
- A few older problems still carry `audit.py` <5-edge warnings (allowed, not blocking); backfill when convenient.
- The templates' `CLAUDE.md`/dead_ends still carry some **v1 history** (pre-Monaco overlay editor) — kept as history.

## Reference Links
- `SOLUTION.md` (authoritative: architecture + authoring rules + §4 mutation standard + difficulty rubric),
  `problems/FORMAT.md` (package format + test standard). Gates: `verify_all.py`, `audit.py`,
  `mutation_test.py`, `gate_candidate.py`. Compression: `compress_bank.py`.
- Hosted: `https://oa123.fly.dev` (Fly v10). Repos: `github.com/RushilJ2603/oa-judge`, `.../oa-problems`.
