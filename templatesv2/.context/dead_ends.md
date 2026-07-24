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
