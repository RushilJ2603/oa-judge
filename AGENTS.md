# OA Judge — repo orientation (for delegated agents)

A local LeetCode/HackerRank-style judge. Python + Flask backend, vanilla JS frontend, C++/Python code
execution. **Standalone project** — do not reference or depend on anything outside this folder.

Key docs:
- `PLAN.md` — what the whole thing is.
- `API.md` — the exact HTTP/JSON contract between frontend and server (build the UI against this).
- `FORMAT.md` — the on-disk format of a `problems/<id>/` package.
- `PACKAGING_BRIEF.md` — per-problem I/O contracts for packaging the migrated questions.
- `problems/flipkart-q1-golden-price/` — a COMPLETE worked example; clone its shape.
- `_migrated_raw/` — the original problem statements + verified reference sources, read-only input.

Hard rules for agents:
- Never create or modify any `reference.cpp` / `reference.py`, nor anything under `tests/hidden/`.
  Those are owned and verified by the orchestrator (Claude).
- Never modify the engine under `app/runner/` or `app/server.py`.
- Everything must run offline: no CDN links, no external network calls, no new pip/npm dependencies.
- Match the exact stdin/stdout format of each problem's existing `reference.*`.
