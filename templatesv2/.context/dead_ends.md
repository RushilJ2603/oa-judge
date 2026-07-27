# dead_ends.md
# ── Approaches Already Ruled Out — DO NOT REVISIT ──────────────
#
# Purpose: This file prevents circular reasoning across sessions.
# Every time an approach is tried and rejected, it is logged here
# with a specific reason. The next AI must read this BEFORE
# suggesting any solutions.
#
# Format:
#   ## [YYYY-MM-DD] — <brief name of approach>
#   **What was tried:** ...
#   **Why rejected:** ... (be specific — not "didn't work")
#   **If user brings it up again:** Remind them of this entry and ask if circumstances changed.

---

## [2026-07-27] — Pushing a bank change to live headless via /api/bank/sync or /api/reindex, or expecting boot to auto-pull
**What was tried:** After pushing the bank, tried to update the live app by (a) `curl -X POST /api/bank/sync` and (b) assuming a `fly apps restart` / cold boot would git-pull and reindex.
**Why rejected:** (a) **Every `/api/` write route requires GitHub OAuth** (`before_request` 401s anything not in `_PUBLIC_PATHS`), so sync/reindex can't be driven headless. (b) The app does **NOT** auto-pull on boot and only reindexes if the index is **empty** (`_ensure_index`), so a restart with a populated DB is a no-op. The intended path is the logged-in UI's Sync button. **Headless recipe that works:** `fly ssh console -a oa123 -C "git -C /data/problems -c safe.directory=/data/problems pull --ff-only origin main"` then rebuild the index against the shared SQLite file: `fly ssh ... -C "sh -c 'cd /app/app && OAJ_DB=/data/judge.db OAJ_PROBLEMS_DIR=/data/problems python3 -c \"import store; from runner import problems; store.reindex_problems(problems.all_meta())\"'"`. Two gotchas that bit me: the ad-hoc ssh session needs `-c safe.directory=/data/problems` inline (the Dockerfile's global config is for the app's runtime user, not root-ssh); and the module is **`runner.problems`, not `problems`** (there is no top-level problems.py — server does `from runner import ... problems`). Also: `fly ssh` fails with "no started VMs" when scaled to zero — hit `/api/health` first to auto-start.
**If user brings it up again:** Use the ssh pull+reindex recipe above (or the logged-in Sync button). Don't expect curl or a bare restart to move live.

## [2026-07-27] — Trusting a transcribed OA sample as ground truth (Q6 maximize-binary-reverse-append)
**What was tried:** The user-supplied Q6 stated sample 1 as: input `00001` → optimal permutation `00001`.
**Why rejected:** Under the reverse-then-append procedure (confirmed by the user's OWN example-2 walkthrough), `00001` produces final `00001`, but `00010` produces `10000` which is **strictly larger** — so the transcribed "optimal" was wrong. The procedure is a fixed position-permutation, so the max final string is the multiset sorted descending and the answer is its unique preimage. Verified by exhaustive brute-force over ALL permutations for every binary string of length 1..9 (0 theory failures, optimum always unique). Shipped the corrected sample (`00010`).
**If user brings it up again:** For authored problems, the reference + an exhaustive/independent brute is the ground truth, not a transcribed sample — this is the verification-discipline rule. Re-derive, don't trust the photo.

## [2026-07-26] — Populating the live volume bank without a real .git (breaks Sync silently)
**What was tried:** `sharing.ensure_seeded()` copied the seed bank onto `/data/problems`, and we assumed the in-app **Sync** (`git fetch` + `merge --ff-only`) would then keep it current.
**Why rejected:** The volume copy ended up **without a usable `.git`**, so `sharing.sync()` returned `"problems/ is not a git checkout — nothing to sync"` and **every bank push after the seed never reached the live app** — it sat at 122 problems while origin had 123+. The symptom the user saw was "the new problems / the multi-site contest change aren't showing." Fix: because `oa-problems` is **public**, git-clone it fresh onto the volume as a real checkout (`fly ssh` → clone to a temp dir → swap into `/data/problems` → `fly apps restart`, which reindexes on boot). The DB (`/data/judge.db`) is a separate file so personal data is untouched.
**If user brings it up again:** After seeding, VERIFY the volume bank is a git checkout (`git -C /data/problems rev-parse HEAD`); if not, re-clone. Sync (or `fly ssh git pull`) only works on a real checkout.

## [2026-07-26] — LeetCode's /contest/api/list/ REST endpoint for upcoming contests
**What was tried:** Fetching upcoming LeetCode contests from `https://leetcode.com/contest/api/list/` for the tracker's multi-site feed.
**Why rejected:** It returns **HTTP 403 Forbidden** to the server (bot protection), same as LC's other REST/HTML surfaces. Fix: use the **GraphQL** endpoint instead — `POST https://leetcode.com/graphql` with `query{upcomingContests{title titleSlug startTime duration}}` is NOT blocked (it's the same endpoint already used for LC user stats). AtCoder (page scrape), CodeChef (`/api/list/contests/all`), and CF (`contest.list`) all work keyless; each fetcher is best-effort so one site failing never blanks the others.
**If user brings it up again:** For any LeetCode data from the server, prefer the GraphQL endpoint; the REST/HTML endpoints 403. (This is consistent with the earlier note that LC problem links can't be curl/WebFetch-verified.)

## [2026-07-25] — Treating a mutant TIMEOUT as "skip this input" instead of a kill
**What was tried:** To stop the mutation score flapping under CPU load, `mutation_test.run()` returned a `<TIMEOUT>` sentinel and `killed_by` SKIPPED any input where the mutant timed out (don't count it as a kill).
**Why rejected:** A mutant that flips a loop counter (`i++`→`i--`) infinite-loops on EVERY input, so skipping made it survive `killed_by`, then `find_distinguisher` re-ran it against ~80 generator inputs, each hitting the 25s timeout → a >30-minute hang per such mutant. The real fix is a RELIABLE ORACLE (retry the reference at 4× timeout, then DROP any input it still can't finish); given that, every kept input is reference-tractable, so a mutant timeout/crash there is a genuine TLE/crash = **KILL** (confirmed with one larger-budget retry to rule out a load blip). Per-mutant timeout is adaptive (`max(6, min(25, 15×max_ref_seconds))`).
**If user brings it up again:** Don't skip mutant timeouts. Make the oracle reliable first; then timeout/crash on a tractable input IS a kill. And never run two heavy mutation processes at once — that OOM-crashed the 10GB WSL VM (cap `OAJ_MUT_WORKERS`).

## [2026-07-25] — Fuzzing any token (incl. count fields) and reading a reference crash as empty output
**What was tried:** The ±1 fuzzer (equivalent-vs-gap triage) perturbed every integer token of an input, and `run()` returned the reference's stdout regardless of exit code.
**Why rejected:** Perturbing a COUNT/header field (leading `N`, or `r`→`r>M`) desyncs the input grammar or drives the otherwise-correct reference out of bounds → it crashes (SIGSEGV) or misparses. `run()` read that crash as `stdout=""`, so any non-crashing mutant "differed" from `""` and a harmless `i<n`→`i<=n` mutant looked killable — a PHANTOM GAP that would persist an invalid edge test (make_hidden then drops it with rc=-11). Fix: fuzz PAYLOAD rows only (lines with ≥3 numeric tokens), never a header/count line or the first token; and `run()` returns `<ERR rc=N>` on a non-zero exit so the oracle DROPS crash inputs and triage SKIPS them.
**If user brings it up again:** A distinguisher must be a VALID in-grammar input on which the reference succeeds; watch for `EDGE reference FAILED … rc=-11` in make_hidden as the tell of an out-of-range fuzz gap.

## [2026-07-25] — Letting a Python-only reference pass the gate (mutation silently skipped)
**What was tried:** Running the full gate on a package whose reference is `reference.py` (needed for bignum output, e.g. Decode-Ways count). `mutation_test.py` only mutates C++, so it printed `SKIP (no reference.cpp)` and exited 0 — `gate_candidate.py` counted that as a mutation PASS.
**Why rejected:** A skipped strength check reading as PASS is exactly the "bugged code passes 17/18 tests" failure the gate exists to prevent — the suite's strength is UNVERIFIED. `gate_candidate.py` now HARD-FAILS on a mutation SKIP. `valid-number-partitions` was correctly deferred (not merged).
**If user brings it up again:** A problem needs a C++ reference to be certified; to ship a bignum/Python one, convert to mod-1e9+7 C++ (re-anchor) or add Python-mutation support to the gate — never merge on anchor+brute alone.

## [2026-07-24] — Baking the problem bank only into the Docker image on a scale-to-zero host
**What was tried:** Hosting `oa-problems` at `/problems` (image filesystem) with `OAJ_PROBLEMS_DIR=/problems`, expecting the in-app **Sync** (`git pull`) to keep it current.
**Why rejected:** Fly `auto_stop_machines` stops the machine on idle; the next request cold-starts from the **baked image**, discarding pulled commits — while the search index on the persistent volume stayed newer. Symptom: "have to click Sync several times / new problems don't stick." Fix: put the LIVE bank on the persistent volume (`OAJ_PROBLEMS_DIR=/data/problems`), seeded once from the baked `/problems` by `sharing.ensure_seeded()`.
**If user brings it up again:** On a scale-to-zero host, anything that must survive restarts (DB *and* the bank) goes on the volume; the image is a read-only seed only.

## [2026-07-24] — Sending the TUF+ Bearer token to the SSR HTML page to unlock premium fields
**What was tried:** Scraper fetched `takeuforward.org/.../problems/<slug>` with `Authorization: Bearer <token>` and parsed the Next.js RSC flight payload, expecting ungated difficulty/tags/editorial.
**Why rejected:** The SSR page stays gated even when authenticated; TUF+ serves ungated premium data from a **separate authenticated API** (`https://backend-go.takeuforward.org`, verified via `/api/v1/auth/me` → `logged_in:true`). Fix: call `GET /api/v2/plus/problem/{slug}?subjectSlug=dsa` with the Bearer token; keep the HTML parse as anonymous fallback.
**If user brings it up again:** For TUF+ premium, hit the backend-go API with the Bearer token; the HTML page alone never carries the ungated content.

## [2026-07-24] — Trusting a scraped site's "official" solution as the reference without checking its samples
**What was tried:** Considered using OA-Helper's provided `solution_cpp` directly as the judged reference.
**Why rejected:** Some are wrong — #8 Square Tile Arrangement's official solution returns 18 for input `0 18` whose expected output is 8 (its own solution disagrees with its own sample). Blindly trusting it ships a broken judge. Fix: always write/verify an independent reference, cross-check it against the site's provided samples AND an independent brute force; skip problems whose semantics can't be pinned down.
**If user brings it up again:** A scraped solution is a hint, never the source of truth; the reference must pass provided samples + a brute-force cross-check.

## [2026-07-24] — Assuming OA-Helper uses a Supabase user JWT for premium auth
**What was tried:** Told the user to grab a Supabase `sb-…-auth-token` from localStorage to unlock premium OA-Helper content.
**Why rejected:** OA-Helper uses **cookie-based session auth** (`oahelper_user.session_cookie_auth:true`, empty token) — no Supabase JWT exists in localStorage. Premium content is served by `oahelper.in`'s own backend, authenticated by the HTTP-only **`oa_session`** cookie, via `GET /api/proxy/question?action=get_question&question_ref=base64("{id}|0")`. Anon Supabase reads statements but nulls premium solutions/editorials/tests.
**If user brings it up again:** OA-Helper auth = the `oa_session` cookie (+ device id/signature), not a Supabase token; premium content comes from the site's `/api/proxy/question` proxy.

## [2026-07-23] — CodeMirror / any CDN-loaded editor for syntax highlighting
**What was tried:** Considered a real editor library (CodeMirror) for the code editor.
**Why rejected:** Hard offline constraint — no CDN, no external network, no new pip/npm deps, and no Node build step in this project. Instead: an enhanced `<textarea>` with a transparent-overlay `<pre>` highlighted by a hand-written tokenizer (`app/static/app.js`), verified lossless so the colored layer stays caret-aligned.
**If user brings it up again:** Only reconsider if the offline/no-build constraint is lifted; otherwise the overlay approach already delivers coloring with zero dependencies.

## [2026-07-23] — String-category size hints in problem generators ("small"/"medium"/"large")
**What was tried:** Some generators read `argv[2]` as a category string.
**Why rejected:** The tooling (`make_hidden.py`, `stress.py`) passes an INTEGER size. `"8" != "large"` fell through to the large branch → generators emitted up-to-1,000,000-char inputs, making hidden tests huge and stress counterexamples unreadable. Standard is now `argv[2]=int size`, small default.
**If user brings it up again:** Don't reintroduce categorical sizes; keep the integer contract in FORMAT.md.

## [2026-07-23] — Recompiling the reference inside the stress loop
**What was tried:** `stress.py` originally compiled the reference on every iteration.
**Why rejected:** ~1000 compilations per run (300 iters + shrink) → the request timed out (>120s), especially on the slow `/mnt/c` mount. Fixed: compile reference (and user) exactly once, reuse the binary; also skip the shrink phase when the first counterexample is already ≤40 chars.
**If user brings it up again:** Never recompile per-iteration; compile-once is required for acceptable latency.

## [2026-07-23] — Testing the Desktop launcher by invoking `wsl.exe` from inside WSL
**What was tried:** Running `cmd.exe /c start wsl.exe -e bash …` and `wsl.exe -e bash _serve.sh` from within the WSL session to simulate a Desktop double-click.
**Why rejected:** Nested `wsl.exe` re-entry from inside WSL does not start the server the way a genuine Windows Explorer double-click does — the test is an artifact, not a real signal. Verified each underlying component instead: `_serve.sh` starts a server the Windows side reaches (PowerShell `Invoke-WebRequest` → HTTP 200), login shell finds flask+g++, `.lnk` targets are correct.
**If user brings it up again:** To truly test the click, do it from Windows Explorer; don't trust nested-wsl results.

## [2026-07-23] — Machine-verifying LeetCode/GfG links via curl or WebFetch
**What was tried:** Corroborating the research agent's LC/GfG URLs by fetching them.
**Why rejected:** LeetCode returns HTTP 403 to both `curl` and `WebFetch` (bot protection) — impossible to confirm a slug exists programmatically here. Links were curated by hand-confidence (kept only canonical problems, dropped uncertain ones; 4 problems have none). They remain **unverified**.
**If user brings it up again:** Either accept unverified links or verify manually in a real browser; automated fetching won't work from this environment.

## [2026-07-23] — Fractional font-size / ratio line-height on the highlight-overlay editor
**What was tried:** The editor's `<textarea>` and highlight `<pre>` used `font-size: 13.5px; line-height: 1.55`.
**Why rejected:** Non-integer per-line box heights round slightly differently between the two elements and the error accumulates down the document — after pasting a block, the visible highlight drifted a line off from the (transparent) caret, so edits landed on the line below what you saw. Fixed by using an integer pixel metric (`13px / 20px`) on the textarea, the `<pre>`, and the line-number gutter, so every line box is identical. Verified with a 25-line overlay screenshot (zero drift).
**If user brings it up again:** Keep the editor metrics as fixed integer px on all three layers; never reintroduce fractional font-size or ratio line-height on the overlay.

---
<!-- Add new entries above this line, newest first -->
