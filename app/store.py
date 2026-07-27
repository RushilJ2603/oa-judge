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


# ------------------------------------------------------------------ bug reports
def add_bug_report(problem_id: str, message: str) -> int:
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO bug_report (problem_id, user_id, message, created_at) VALUES (?,?,?,?)",
        (problem_id, _uid(), message, _now()))
    conn.commit()
    return cur.lastrowid


def bug_reports(limit: int = 300, status: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM bug_report", []
    if status:
        q += " WHERE status = ?"
        args.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in db.connect().execute(q, args).fetchall()]


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


# ------------------------------------------------------------------ problem index (search at scale)
# The sidebar can't load thousands of problems at once, so we cache their metadata in problem_index
# (rebuilt from disk on startup + after each Sync) and serve a paginated, filtered search from it.
# Top-level groups shown in the sidebar, in display order. `gyan` is the legacy key for the
# personally-curated collection — kept as-is on disk (19 problems), shown as "Iris — Personal".
SOURCE_LABELS = {"tuf": "TUF+", "oa-helper": "OA-Helper", "gyan": "Iris — Personal"}
SOURCE_ORDER = ["tuf", "oa-helper", "gyan"]

# Canonicalize company names so the sidebar doesn't split one company across casings/aliases, and so
# every unknown/unlabelled problem lands in a single "Practice" bucket. Applied at index time.
_COMPANY_CANON = {
    "de shaw": "DE Shaw",
    "algouniversity": "Algo University", "algo university": "Algo University",
    "trilogy": "Trilogy Innovations", "trilogy innovations": "Trilogy Innovations",
    "bny": "BNY Mellon", "bny mellon": "BNY Mellon",
    "cisco code": "Cisco",
}
_UNKNOWN_COMPANY = {"", "unknown", "unknown oa", "n/a", "na", "none", "-", "?"}


def canon_company(c: str) -> str:
    c = (c or "").strip()
    if c.lower() in _UNKNOWN_COMPANY:
        return "Practice"
    return _COMPANY_CANON.get(c.lower(), c)


def reindex_problems(metas: list[dict]) -> int:
    """Replace the whole problem_index with the current on-disk metadata. Idempotent; cheap."""
    conn = db.connect()
    now = _now()
    conn.execute("DELETE FROM problem_index")
    conn.executemany(
        "INSERT INTO problem_index"
        " (id, title, title_lc, difficulty, company, source, topic, tags_json, runnable,"
        "  languages_json, indexed_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(m["id"], m["title"], (m["title"] or "").lower(), m.get("difficulty", ""),
          canon_company(m.get("company", "")), m.get("source", "gyan"), m.get("topic", ""),
          json.dumps(m.get("tags", [])), 1 if m.get("runnable", True) else 0,
          json.dumps(m.get("languages", [])), now)
         for m in metas])
    conn.commit()
    return len(metas)


def index_count() -> int:
    return db.connect().execute("SELECT COUNT(*) AS n FROM problem_index").fetchone()["n"]


def _search_where(source, company, difficulty, topic, q):
    clauses, args = [], []
    if source:
        clauses.append("source = ?"); args.append(source)
    if company:
        clauses.append("company = ?"); args.append(company)
    if difficulty:
        clauses.append("difficulty = ?"); args.append(difficulty)
    if topic:
        clauses.append("topic = ?"); args.append(topic)
    if q:
        # match title, topic, tags, company or id — case-insensitive substring. Topic is included so
        # a solver can FIND problems by topic (search "graphs"/"dp"), even though the topic is hidden
        # on the problem view itself (seeing it would give away the intended approach).
        like = f"%{q.lower()}%"
        clauses.append("(title_lc LIKE ? OR lower(topic) LIKE ? OR lower(tags_json) LIKE ?"
                       " OR lower(company) LIKE ? OR lower(id) LIKE ?)")
        args += [like, like, like, like, like]
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", args


def _hydrate(rows, solved_set):
    out = []
    for r in rows:
        r = dict(r)
        r["tags"] = json.loads(r.pop("tags_json") or "[]")
        r["languages"] = json.loads(r.pop("languages_json") or "[]")
        r["runnable"] = bool(r["runnable"])
        r["solved"] = r["id"] in solved_set
        out.append(r)
    return out


_SEL = ("SELECT id, title, difficulty, company, source, topic, tags_json, runnable, languages_json"
        " FROM problem_index")


def search_problems(source=None, company=None, difficulty=None, topic=None, q=None,
                    solved=None, page=1, page_size=50, sort="title") -> dict:
    """Paginated, filtered problem list from the index, annotated with the user's solved set.
    `solved` filter: 'solved' | 'unsolved' | None."""
    conn = db.connect()
    where, args = _search_where(source, company, difficulty, topic, q)
    order = "title_lc ASC" if sort == "title" else "indexed_at DESC, id DESC"
    solved_set = solved_ids()

    if solved in ("solved", "unsolved"):
        # solved status is per-user (not in SQL): fetch matches, filter, then paginate in Python.
        rows = _hydrate(conn.execute(f"{_SEL}{where} ORDER BY {order}", args).fetchall(), solved_set)
        want = (solved == "solved")
        rows = [r for r in rows if r["solved"] == want]
        total = len(rows)
        start = (page - 1) * page_size
        return {"problems": rows[start:start + page_size], "total": total,
                "page": page, "page_size": page_size}

    total = conn.execute(f"SELECT COUNT(*) AS n FROM problem_index{where}", args).fetchone()["n"]
    start = (page - 1) * page_size
    rows = conn.execute(f"{_SEL}{where} ORDER BY {order} LIMIT ? OFFSET ?",
                        args + [page_size, start]).fetchall()
    return {"problems": _hydrate(rows, solved_set), "total": total,
            "page": page, "page_size": page_size}


def problem_facets() -> dict:
    """Counts for the sidebar's grouping/filters: per source, per company, per difficulty, plus how
    many the current user has solved in each source."""
    conn = db.connect()
    solved_set = solved_ids()
    sources = [dict(r) for r in conn.execute(
        "SELECT source, COUNT(*) AS n FROM problem_index GROUP BY source ORDER BY source")]
    companies = [dict(r) for r in conn.execute(
        "SELECT company, COUNT(*) AS n FROM problem_index WHERE company != ''"
        " GROUP BY company ORDER BY n DESC, company")]
    # Companies grouped under their source — the nested source ▸ company dropdown in the sidebar.
    companies_by_source: dict[str, list] = {}
    for r in conn.execute(
            "SELECT source, company, COUNT(*) AS n FROM problem_index WHERE company != ''"
            " GROUP BY source, company ORDER BY n DESC, company"):
        companies_by_source.setdefault(r["source"], []).append(
            {"company": r["company"], "n": r["n"]})
    difficulties = {r["difficulty"]: r["n"] for r in conn.execute(
        "SELECT difficulty, COUNT(*) AS n FROM problem_index GROUP BY difficulty")}
    # solved-per-source needs the user's solved set (kept out of SQL for portability)
    solved_by_source = {}
    for r in conn.execute("SELECT id, source FROM problem_index"):
        if r["id"] in solved_set:
            solved_by_source[r["source"]] = solved_by_source.get(r["source"], 0) + 1
    # Order the top-level groups by SOURCE_ORDER (known sources first), then any unknown source.
    src_rank = {k: i for i, k in enumerate(SOURCE_ORDER)}
    sources.sort(key=lambda s: (src_rank.get(s["source"], len(SOURCE_ORDER)), s["source"]))
    return {
        "sources": [{"key": s["source"], "label": SOURCE_LABELS.get(s["source"], s["source"]),
                     "count": s["n"], "solved": solved_by_source.get(s["source"], 0),
                     "companies": companies_by_source.get(s["source"], [])} for s in sources],
        "companies": companies,
        "difficulties": difficulties,
        "total": index_count(),
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


# ------------------------------------------------------------------ presence (best-effort, $0)
def touch_user(user_id: int) -> None:
    """Record that this user just made a request. Called from real API traffic (no heartbeat), so
    presence costs nothing and never keeps the scale-to-zero machine awake on its own."""
    conn = db.connect()
    conn.execute("UPDATE \"user\" SET last_seen = ? WHERE id = ?", (_now(), user_id))
    conn.commit()


def online_users(within_seconds: int = 300) -> list[dict]:
    """Users seen within the window, most-recent first. 'Online' = made a request recently; someone
    with an idle tab open (no requests) will age out — detecting them would need a heartbeat, which
    isn't free. Timestamps are ISO-8601 UTC, so a string compare is a correct time compare."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=within_seconds)).isoformat(timespec="seconds")
    rows = db.connect().execute(
        "SELECT id, login, name, avatar_url, last_seen FROM \"user\""
        " WHERE last_seen IS NOT NULL AND last_seen >= ? ORDER BY last_seen DESC",
        (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def presence_recent(within_seconds: int = 30 * 86400, limit: int = 60) -> list[dict]:
    """The shared 'who's been around' history — every user seen within the window (default 30 days),
    most-recent first. Visible to all users. Same cheap read as online_users (no heartbeat), just a
    wider window + a cap so the modal stays bounded."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=within_seconds)).isoformat(timespec="seconds")
    rows = db.connect().execute(
        "SELECT id, login, name, avatar_url, last_seen FROM \"user\""
        " WHERE last_seen IS NOT NULL AND last_seen >= ? ORDER BY last_seen DESC LIMIT ?",
        (cutoff, limit)).fetchall()
    return [dict(r) for r in rows]


# ============================================================ CP + System Design sheets
# Data access for the two "sheets", the per-user checklist that rides them, linked CP handles,
# cached stats, cached upcoming contests, and the rating goal. Network fetchers and the
# deterministic tracker maths live in cp.py; this stays pure DB.

def sheet_progress() -> dict:
    """{item_id: status} for the current user across every sheet."""
    rows = db.connect().execute(
        "SELECT item_id, status FROM sheet_progress WHERE user_id = ?", (_uid(),)).fetchall()
    return {r["item_id"]: r["status"] for r in rows}


def set_sheet_item(item_id: str, status: str = "done") -> None:
    conn = db.connect()
    conn.execute(
        "INSERT INTO sheet_progress (user_id, item_id, status, updated_at) VALUES (?,?,?,?)"
        " ON CONFLICT (user_id, item_id) DO UPDATE SET status = excluded.status,"
        " updated_at = excluded.updated_at",
        (_uid(), item_id, status, _now()))
    conn.commit()


def clear_sheet_item(item_id: str) -> None:
    conn = db.connect()
    conn.execute("DELETE FROM sheet_progress WHERE user_id = ? AND item_id = ?", (_uid(), item_id))
    conn.commit()


def sheet_code_get(item_id: str) -> dict:
    """The current user's scratchpad {lang, code} for a sheet item; empty defaults if none yet."""
    row = db.connect().execute(
        "SELECT lang, code FROM sheet_code WHERE user_id = ? AND item_id = ?",
        (_uid(), item_id)).fetchone()
    return {"lang": row["lang"], "code": row["code"]} if row else {"lang": "cpp", "code": ""}


def set_sheet_code(item_id: str, lang: str, code: str) -> None:
    """Upsert the scratchpad. An empty code with the default lang clears the row so we don't keep
    blank scratchpads around."""
    conn = db.connect()
    if not (code or "").strip() and (lang or "cpp") == "cpp":
        conn.execute("DELETE FROM sheet_code WHERE user_id = ? AND item_id = ?", (_uid(), item_id))
    else:
        conn.execute(
            "INSERT INTO sheet_code (user_id, item_id, lang, code, updated_at) VALUES (?,?,?,?,?)"
            " ON CONFLICT (user_id, item_id) DO UPDATE SET lang = excluded.lang,"
            " code = excluded.code, updated_at = excluded.updated_at",
            (_uid(), item_id, lang or "cpp", code or "", _now()))
    conn.commit()


def cp_handles() -> dict:
    rows = db.connect().execute(
        "SELECT site, handle FROM cp_handle WHERE user_id = ?", (_uid(),)).fetchall()
    return {r["site"]: r["handle"] for r in rows}


def set_cp_handle(site: str, handle: str) -> None:
    conn = db.connect()
    if not handle:
        conn.execute("DELETE FROM cp_handle WHERE user_id = ? AND site = ?", (_uid(), site))
    else:
        conn.execute(
            "INSERT INTO cp_handle (user_id, site, handle, updated_at) VALUES (?,?,?,?)"
            " ON CONFLICT (user_id, site) DO UPDATE SET handle = excluded.handle,"
            " updated_at = excluded.updated_at",
            (_uid(), site, handle.strip(), _now()))
    conn.commit()


def cp_stats_cache_get(site: str) -> dict | None:
    r = db.connect().execute(
        "SELECT payload, ok, fetched_at FROM cp_stats_cache WHERE user_id = ? AND site = ?",
        (_uid(), site)).fetchone()
    if not r:
        return None
    try:
        payload = json.loads(r["payload"])
    except Exception:
        payload = None
    return {"payload": payload, "ok": bool(r["ok"]), "fetched_at": r["fetched_at"]}


def cp_stats_cache_put(site: str, payload: dict, ok: bool = True) -> None:
    conn = db.connect()
    conn.execute(
        "INSERT INTO cp_stats_cache (user_id, site, payload, ok, fetched_at) VALUES (?,?,?,?,?)"
        " ON CONFLICT (user_id, site) DO UPDATE SET payload = excluded.payload,"
        " ok = excluded.ok, fetched_at = excluded.fetched_at",
        (_uid(), site, json.dumps(payload), 1 if ok else 0, _now()))
    conn.commit()


def contests_get(limit: int = 60) -> list[dict]:
    rows = db.connect().execute(
        "SELECT site, name, url, start_at, duration_min FROM contest_cache"
        " ORDER BY start_at LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def contests_age_seconds() -> float | None:
    r = db.connect().execute("SELECT MAX(fetched_at) AS f FROM contest_cache").fetchone()
    if not r or not r["f"]:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(r["f"])).total_seconds()
    except Exception:
        return None


def contests_replace(rows: list[dict]) -> None:
    """Swap the global upcoming-contest cache in one transaction."""
    conn = db.connect()
    now = _now()
    conn.execute("DELETE FROM contest_cache")
    conn.executemany(
        "INSERT INTO contest_cache (site, name, url, start_at, duration_min, fetched_at)"
        " VALUES (?,?,?,?,?,?)",
        [(r["site"], r["name"], r["url"], r["start_at"], r.get("duration_min"), now) for r in rows])
    conn.commit()


def cp_goal() -> dict:
    r = db.connect().execute(
        "SELECT target_rating, deadline, start_rating, start_at, pace_per_day FROM cp_goal"
        " WHERE user_id = ?", (_uid(),)).fetchone()
    if not r:
        return {"target_rating": 1900, "deadline": "2027-05-31", "start_rating": None,
                "start_at": None, "pace_per_day": 3}
    return dict(r)


def set_cp_goal(target_rating=None, deadline=None, start_rating=None, start_at=None,
                pace_per_day=None) -> None:
    cur = cp_goal()
    conn = db.connect()
    conn.execute(
        "INSERT INTO cp_goal (user_id, target_rating, deadline, start_rating, start_at,"
        " pace_per_day, updated_at) VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT (user_id) DO UPDATE SET target_rating = excluded.target_rating,"
        " deadline = excluded.deadline, start_rating = excluded.start_rating,"
        " start_at = excluded.start_at, pace_per_day = excluded.pace_per_day,"
        " updated_at = excluded.updated_at",
        (_uid(),
         target_rating if target_rating is not None else cur["target_rating"],
         deadline if deadline is not None else cur["deadline"],
         start_rating if start_rating is not None else cur["start_rating"],
         start_at if start_at is not None else cur["start_at"],
         pace_per_day if pace_per_day is not None else cur["pace_per_day"],
         _now()))
    conn.commit()
