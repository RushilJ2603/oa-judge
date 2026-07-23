# Session Prompts — Copy & Paste Ready
# ── For use in Antigravity IDE / Claude Code ────────────────────

## ★ PROJECT INIT PROMPT  ← START HERE for a brand new project
# Paste this ONCE when you first copy the templates into a new project.
# The AI will explore the codebase and fill in all the blank template files.

---

I've just copied blank context templates into this project. Your job is to fill them in by exploring the codebase — do NOT ask me to fill them in manually.

Work through the following in order:

**1. Fill in `CLAUDE.md`**
Explore the project root, `src/`, `package.json` / `pyproject.toml` / `requirements.txt`, any existing `README.md`, and key config files. Replace every `<!-- placeholder -->` comment with real information. Leave the Behavioral Guidelines and Session Protocol sections exactly as they are — only fill in project-specific sections (What This Project Does, Tech Stack, Directory Map, Coding Rules, How to Run, Key Reference Files, Files Never Touch).

**2. Fill in `PROJECT_STATE.md`**
Based on what you found: what phase is this project in? What appears to be working vs. incomplete? What would a reasonable next step be? Fill in every field. If something is genuinely unknown, write `Unknown — ask user` rather than leaving it blank.

**3. Create `CHANGELOG.md`** (if it doesn't exist)
Create it with a single bootstrap entry:
```
## [YYYY-MM-DD HH:MM IST] — Project context initialized | By: AI
- Copied context templates and filled them based on codebase exploration.
- No code changes made.
```

**4. Leave `.context/dead_ends.md`, `.context/session.json`, and `SESSION_LOG.md` as-is** — these get populated during actual work sessions. Do NOT create `.context/sessions/` (the archive folder) — it's created automatically when the first session ends.

After filling all files, respond with:
- What you found and filled in (3–5 bullets)
- Anything you couldn't determine from the codebase alone (ask me these)
- Whether anything looked broken or inconsistent

Do NOT make any changes to actual source code during this init.

---


## SESSION START PROMPT
# Paste this as your first message when opening a new AI session on this project.

---

You are being onboarded onto an active project. Before doing anything else, read these files in this exact order:

1. `CLAUDE.md` — Project rules and your behavioral constraints
2. `PROJECT_STATE.md` — Where the project stands right now
3. `.context/session.json` — Machine-readable state from the last session
4. `.context/dead_ends.md` — Approaches that have been RULED OUT (read carefully)
5. Last **3 entries only** of `CHANGELOG.md` (most recent first)

After reading all five files, respond with:
- **3-bullet summary** of your understanding of the current state
- **The single next action** you recommend we take
- **Any ambiguities or conflicts** you noticed across the documents

Do NOT start any work until the user explicitly confirms your understanding is correct.

---


## SESSION END PROMPT
# Paste this before closing the session so the AI updates all context files.

---

Before we close this session, please do the following in order:

**1. Update `PROJECT_STATE.md`:**
- Set "Last Updated" to the current date and time (IST) and your name
- Update "Current Status" to reflect what we just did
- Update "Next Session Must Start With" to the precise next action
- Update "Blocking Issues" accordingly

**2. Prepend a new entry to `CHANGELOG.md`:**
```
## [YYYY-MM-DD HH:MM IST] — <one-line summary of what happened> | By: [Name]

### Done This Session
- <specific thing 1 that was completed>
- <specific thing 2>

### Errors Hit
- <error and how it was resolved, or "None">

### Next Session Must
- <specific action 1 the next session must take>
```

**3. Append to `.context/dead_ends.md`** if any approach was tried and ruled out this session.

**4. Archive then regenerate `.context/session.json`:**
- First, copy the existing `.context/session.json` to `.context/sessions/<generated_at-ISO>.json` using the `generated_at` timestamp from inside the file (replace `:` with `-` for filesystem safety, e.g. `2026-05-28T22-23-00+0530.json`). Create `.context/sessions/` if it doesn't exist.
- Then regenerate `.context/session.json` with this session's data, using the schema at the top of that file. Fill all fields accurately. The canonical path always holds the LATEST session — history lives in the archive folder.

**5. Prepend a detailed entry to `SESSION_LOG.md`** — this is the user's personal journal, not an AI handoff file. It must be verbose and honest. Required in every entry:
- Exact **date AND time** for both start and end of the session (with timezone)
- **Exact file paths** of every file touched (not vague summaries — full paths with line numbers where useful)
- What went right, what went wrong, what got redone, what you were uncertain about
- Follow the template/format already at the bottom of `SESSION_LOG.md`

**6. Commit all modified files (do NOT push):**
```bash
git add CHANGELOG.md PROJECT_STATE.md SESSION_LOG.md .context/session.json .context/sessions/ .context/dead_ends.md
git commit -m "session: <same one-line summary as changelog>"
```
Only push if the user explicitly asks. Otherwise leave the commits local.

Confirm when done.

---


## QUICK ONBOARD PROMPT (shorter — for simple sessions)
# Use this when you don't need the full ritual.

---

Read `PROJECT_STATE.md` and `.context/session.json`, then give me a 2-sentence status summary and the next recommended action. Wait for my go-ahead before doing anything.

---


## DEAD END REGISTRATION PROMPT
# Paste this whenever an approach is ruled out mid-session.

---

Please add the following to `.context/dead_ends.md` (prepend, newest first):

**What was tried:** [describe approach]
**Why rejected:** [specific reason — not vague]
**If brought up again:** [what the AI should say]

---
