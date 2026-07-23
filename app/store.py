"""Data access for OA Judge v2 — replaces runner/history.py.

Everything the user produces lands here: submitted code, runs, live drafts, snapshots of
half-written code, OA session timings, notes and flags. v1 stored only attempt *metadata*
in a flat JSON file and threw the source away; that is the gap this module closes.

SQL is kept standard (no INSERT OR REPLACE, no SQLite-only functions) so Phase 6 can move
to Postgres by swapping the driver. Timestamps are ISO-8601 UTC strings, which sort
lexicographically and carry no timezone ambiguity.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import db

# Keep the tail of long outputs out of the DB; the full thing is rarely useful and
# a runaway program can emit megabytes.
SNIPPET_LIMIT = 8000
RUNS_KEPT_PER_PROBLEM = 200

# The implicit owner of all data on a single-user local install (see migration 002).
LOCAL_USER_ID = 1

# Every personal read/write is scoped to "the current user". In hosted mode the server sets a
# provider that returns the logged-in user's id (from the request session); locally it stays the
# implicit local user, so nothing about single-user use changes. Kept as a plain callable so this
# module never imports Flask and stays usable from scripts/tests.
_user_provider = lambda: LOCAL_USER_ID  # noqa: E731


def set_user_provider(fn) -> None:
    global _user_provider
    _user_provider = fn


def _uid() -> int:
    try:
        u = _user_provider()
        return int(u) if u is not None else LOCAL_USER_ID
    except Exception:
        return LOCAL_USER_ID


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clip(s: str | None, limit: int = SNIPPET_LIMIT) -> str | None:
    if s is None:
        return None
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n... [{len(s) - limit} more chars truncated]"


# ------------------------------------------------------------------ attempts
def record_attempt(problem_id, language, mode, verdict, passed, total,
                   source_code=None, duration_s=None, runtime_ms=None,
                   compile_output=None, first_fail_idx=None,
                   stdout_snippet=None, stderr_snippet=None,
                   imported_from=None, created_at=None) -> int:
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO attempt (user_id, problem_id, language, mode, verdict, passed, total,"
        " duration_s, runtime_ms, source_code, compile_output, first_fail_idx,"
        " stdout_snippet, stderr_snippet, created_at, imported_from)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (_uid(), problem_id, language, mode, verdict, passed, total,
         duration_s, runtime_ms, source_code, _clip(compile_output), first_fail_idx,
         _clip(stdout_snippet), _clip(stderr_snippet), created_at or _now(), imported_from))
    conn.commit()
    return int(cur.lastrowid)


def attempts(problem_id: str | None = None, limit: int = 500) -> list[dict]:
    """Newest first, for the current user only. Excludes source_code (large; list never shows it)."""
    conn = db.connect()
    sql = ("SELECT id, problem_id, language, mode, verdict, passed, total, duration_s,"
           " runtime_ms, first_fail_idx, created_at, imported_from,"
           " CASE WHEN source_code IS NULL THEN 0 ELSE 1 END AS has_code"
           " FROM attempt WHERE user_id = ?")
    args: tuple = (_uid(),)
    if problem_id:
        sql += " AND problem_id = ?"
        args += (problem_id,)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    return [dict(r) for r in conn.execute(sql, args + (limit,))]


def attempt(attempt_id: int) -> dict | None:
    """One attempt including its full source. Scoped to the current user so nobody can read
    another person's code by guessing an id."""
    row = db.connect().execute(
        "SELECT * FROM attempt WHERE id = ? AND user_id = ?",
        (attempt_id, _uid())).fetchone()
    return dict(row) if row else None


def solved_ids() -> set[str]:
    conn = db.connect()
    return {r["problem_id"] for r in conn.execute(
        "SELECT DISTINCT problem_id FROM attempt WHERE verdict = 'AC' AND user_id = ?",
        (_uid(),))}


def revisit_list(all_ids: list[str]) -> list[str]:
    """Attempted-but-never-AC'd first, then never-attempted (for the current user)."""
    conn = db.connect()
    solved = solved_ids()
    attempted = {r["problem_id"] for r in conn.execute(
        "SELECT DISTINCT problem_id FROM attempt WHERE user_id = ?", (_uid(),))}
    failed = [pid for pid in all_ids if pid in attempted and pid not in solved]
    untouched = [pid for pid in all_ids if pid not in attempted]
    return failed + untouched


# ------------------------------------------------------------------ runs
def record_run(problem_id, language, source_code, stdin, stdout, stderr,
               exit_code=None, signal=None, runtime_ms=None, verdict=None) -> int:
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO run (user_id, problem_id, language, source_code, stdin, stdout, stderr,"
        " exit_code, signal, runtime_ms, verdict, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (_uid(), problem_id, language, source_code, _clip(stdin), _clip(stdout), _clip(stderr),
         exit_code, signal, runtime_ms, verdict, _now()))
    conn.commit()
    _prune_runs(problem_id)
    return int(cur.lastrowid)


def _prune_runs(problem_id: str) -> None:
    """Keep only the most recent RUNS_KEPT_PER_PROBLEM rows for this user+problem."""
    conn = db.connect()
    conn.execute(
        "DELETE FROM run WHERE user_id = ? AND problem_id = ? AND id NOT IN ("
        "  SELECT id FROM run WHERE user_id = ? AND problem_id = ? ORDER BY id DESC LIMIT ?)",
        (_uid(), problem_id, _uid(), problem_id, RUNS_KEPT_PER_PROBLEM))
    conn.commit()


def runs(problem_id: str, limit: int = 50) -> list[dict]:
    conn = db.connect()
    return [dict(r) for r in conn.execute(
        "SELECT id, problem_id, language, stdin, stdout, stderr, exit_code, signal,"
        " runtime_ms, verdict, created_at FROM run"
        " WHERE user_id = ? AND problem_id = ? ORDER BY id DESC LIMIT ?",
        (_uid(), problem_id, limit))]


# ------------------------------------------------------------------ drafts
def save_draft(problem_id: str, language: str, source_code: str, cursor_pos=None) -> None:
    """Upsert the current user's live draft. Standard ON CONFLICT so this ports to Postgres."""
    conn = db.connect()
    conn.execute(
        "INSERT INTO draft (user_id, problem_id, language, source_code, cursor_pos, updated_at)"
        " VALUES (?,?,?,?,?,?)"
        " ON CONFLICT (user_id, problem_id, language) DO UPDATE SET"
        "   source_code = excluded.source_code,"
        "   cursor_pos  = excluded.cursor_pos,"
        "   updated_at  = excluded.updated_at",
        (_uid(), problem_id, language, source_code, cursor_pos, _now()))
    conn.commit()


def get_draft(problem_id: str, language: str) -> dict | None:
    row = db.connect().execute(
        "SELECT * FROM draft WHERE user_id = ? AND problem_id = ? AND language = ?",
        (_uid(), problem_id, language)).fetchone()
    return dict(row) if row else None


def all_drafts() -> list[dict]:
    return [dict(r) for r in db.connect().execute(
        "SELECT problem_id, language, length(source_code) AS chars, updated_at"
        " FROM draft WHERE user_id = ? ORDER BY updated_at DESC", (_uid(),))]


# ------------------------------------------------------------------ snapshots
def snapshot_draft(problem_id: str, language: str, source_code: str, reason: str,
                   created_at: str | None = None) -> int | None:
    """Record a point-in-time copy. Skips no-op snapshots (identical to the latest one),
    so the timer does not fill the table while you are reading rather than typing."""
    if source_code is None:
        return None
    conn = db.connect()
    last = conn.execute(
        "SELECT source_code FROM draft_snapshot"
        " WHERE user_id = ? AND problem_id = ? AND language = ? ORDER BY id DESC LIMIT 1",
        (_uid(), problem_id, language)).fetchone()
    if last is not None and last["source_code"] == source_code:
        return None
    cur = conn.execute(
        "INSERT INTO draft_snapshot (user_id, problem_id, language, source_code, reason, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (_uid(), problem_id, language, source_code, reason, created_at or _now()))
    conn.commit()
    return int(cur.lastrowid)


def snapshots(problem_id: str, language: str | None = None, limit: int = 200) -> list[dict]:
    """Oldest first — the scrubber reads left to right through time (current user only)."""
    conn = db.connect()
    sql = ("SELECT id, problem_id, language, reason, created_at,"
           " length(source_code) AS chars FROM draft_snapshot"
           " WHERE user_id = ? AND problem_id = ?")
    args: tuple = (_uid(), problem_id)
    if language:
        sql += " AND language = ?"
        args += (language,)
    sql += " ORDER BY created_at ASC, id ASC LIMIT ?"
    return [dict(r) for r in conn.execute(sql, args + (limit,))]


def snapshot(snapshot_id: int) -> dict | None:
    row = db.connect().execute(
        "SELECT * FROM draft_snapshot WHERE id = ? AND user_id = ?",
        (snapshot_id, _uid())).fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------------ OA sessions
def start_oa_session(problem_id: str) -> int:
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO oa_session (user_id, problem_id, started_at) VALUES (?,?,?)",
        (_uid(), problem_id, _now()))
    conn.commit()
    return int(cur.lastrowid)


def end_oa_session(session_id: int, duration_s=None, result=None, abandoned=False) -> None:
    conn = db.connect()
    conn.execute(
        "UPDATE oa_session SET ended_at = ?, duration_s = ?, result = ?, abandoned = ?"
        " WHERE id = ? AND user_id = ?",
        (_now(), duration_s, result, 1 if abandoned else 0, session_id, _uid()))
    conn.commit()


# ------------------------------------------------------------------ notes / flags / settings
def get_note(problem_id: str) -> str:
    row = db.connect().execute(
        "SELECT body_md FROM note WHERE user_id = ? AND problem_id = ?",
        (_uid(), problem_id)).fetchone()
    return row["body_md"] if row else ""


def save_note(problem_id: str, body_md: str) -> None:
    conn = db.connect()
    conn.execute(
        "INSERT INTO note (user_id, problem_id, body_md, updated_at) VALUES (?,?,?,?)"
        " ON CONFLICT (user_id, problem_id) DO UPDATE SET"
        "   body_md = excluded.body_md, updated_at = excluded.updated_at",
        (_uid(), problem_id, body_md, _now()))
    conn.commit()


def get_flags(problem_id: str) -> dict:
    row = db.connect().execute(
        "SELECT * FROM flag WHERE user_id = ? AND problem_id = ?",
        (_uid(), problem_id)).fetchone()
    return dict(row) if row else {"problem_id": problem_id, "starred": 0,
                                  "revisit": 0, "confidence": None, "last_seen_at": None}


def save_flags(problem_id: str, starred=None, revisit=None, confidence=None) -> None:
    cur = get_flags(problem_id)
    conn = db.connect()
    conn.execute(
        "INSERT INTO flag (user_id, problem_id, starred, revisit, confidence, last_seen_at)"
        " VALUES (?,?,?,?,?,?)"
        " ON CONFLICT (user_id, problem_id) DO UPDATE SET"
        "   starred = excluded.starred, revisit = excluded.revisit,"
        "   confidence = excluded.confidence, last_seen_at = excluded.last_seen_at",
        (_uid(), problem_id,
         cur["starred"] if starred is None else int(bool(starred)),
         cur["revisit"] if revisit is None else int(bool(revisit)),
         cur["confidence"] if confidence is None else confidence,
         _now()))
    conn.commit()


def get_setting(key: str, default=None):
    row = db.connect().execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value) -> None:
    conn = db.connect()
    conn.execute(
        "INSERT INTO setting (key, value) VALUES (?,?)"
        " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value) if not isinstance(value, str) else value))
    conn.commit()


# ------------------------------------------------------------------ stats
def stats() -> dict:
    """Aggregates for the dashboard, for the current user only."""
    conn = db.connect()
    u = _uid()
    row = conn.execute(
        "SELECT COUNT(*) AS total_attempts,"
        " COUNT(DISTINCT problem_id) AS problems_attempted,"
        " SUM(CASE WHEN verdict = 'AC' THEN 1 ELSE 0 END) AS ac_attempts"
        " FROM attempt WHERE user_id = ?", (u,)).fetchone()
    verdicts = {r["verdict"]: r["n"] for r in conn.execute(
        "SELECT verdict, COUNT(*) AS n FROM attempt WHERE user_id = ?"
        " GROUP BY verdict ORDER BY n DESC", (u,))}
    by_lang = {r["language"]: r["n"] for r in conn.execute(
        "SELECT language, COUNT(*) AS n FROM attempt WHERE user_id = ? GROUP BY language", (u,))}
    # Attempts needed to first reach AC, per problem the user eventually solved.
    to_ac = [dict(r) for r in conn.execute(
        "SELECT a.problem_id,"
        "  (SELECT COUNT(*) FROM attempt b"
        "     WHERE b.user_id = a.user_id AND b.problem_id = a.problem_id"
        "       AND b.created_at <= MIN(a.created_at)) AS attempts_to_ac"
        " FROM attempt a WHERE a.verdict = 'AC' AND a.user_id = ? GROUP BY a.problem_id", (u,))]
    solved = solved_ids()
    return {
        "total_attempts": row["total_attempts"] or 0,
        "problems_attempted": row["problems_attempted"] or 0,
        "problems_solved": len(solved),
        "ac_attempts": row["ac_attempts"] or 0,
        "verdicts": verdicts,
        "by_language": by_lang,
        "attempts_to_ac": to_ac,
        "drafts": len(all_drafts()),
        "snapshots": conn.execute(
            "SELECT COUNT(*) AS n FROM draft_snapshot WHERE user_id = ?", (u,)).fetchone()["n"],
        "runs": conn.execute(
            "SELECT COUNT(*) AS n FROM run WHERE user_id = ?", (u,)).fetchone()["n"],
    }


# ------------------------------------------------------------------ users (hosted mode)
def upsert_github_user(github_id: int, login: str, name: str = None, avatar_url: str = None) -> int:
    """Create or update a user from a GitHub profile; returns the local user id."""
    conn = db.connect()
    conn.execute(
        "INSERT INTO \"user\" (github_id, login, name, avatar_url, created_at)"
        " VALUES (?,?,?,?,?)"
        " ON CONFLICT (github_id) DO UPDATE SET"
        "   login = excluded.login, name = excluded.name, avatar_url = excluded.avatar_url",
        (github_id, login, name, avatar_url, _now()))
    conn.commit()
    return int(conn.execute("SELECT id FROM \"user\" WHERE github_id = ?",
                            (github_id,)).fetchone()["id"])


def get_user(user_id: int) -> dict | None:
    row = db.connect().execute(
        "SELECT id, github_id, login, name, avatar_url FROM \"user\" WHERE id = ?",
        (user_id,)).fetchone()
    return dict(row) if row else None
