-- 001_init — OA Judge v2 core schema.
--
-- PORTABILITY CONTRACT (hosting is in scope; see PLAN_V2.md):
--   * types limited to TEXT / INTEGER / REAL  -> map 1:1 onto Postgres
--   * timestamps are TEXT, ISO-8601 UTC       -> lexicographically sortable, tz-safe
--   * booleans are INTEGER 0/1                -> becomes BOOLEAN on PG
--   * "id INTEGER PRIMARY KEY" is the only SQLite-ism; on Postgres it becomes
--     "id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY". One line per table.
--   * no INSERT OR REPLACE anywhere. Upserts use standard
--     "ON CONFLICT (...) DO UPDATE SET", supported by both engines.

-- ---------------------------------------------------------------- problems (cache of disk)
-- Files under problems/<id>/ remain the SOURCE OF TRUTH. This table exists only so the UI can
-- list, search and filter fast, and is rebuilt wholesale on sync. Never author into it.
CREATE TABLE IF NOT EXISTS problem_index (
    id             TEXT PRIMARY KEY,
    title          TEXT NOT NULL,
    difficulty     TEXT,
    company        TEXT,
    tags_json      TEXT NOT NULL DEFAULT '[]',
    source_url     TEXT,
    runnable       INTEGER NOT NULL DEFAULT 0,
    languages_json TEXT NOT NULL DEFAULT '[]',
    time_limit_ms  INTEGER,
    author         TEXT,
    checksum       TEXT,
    indexed_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_problem_company ON problem_index (company);

-- ---------------------------------------------------------------- attempts (one row per SUBMIT)
-- source_code is the whole point of v2: v1 threw the code away after judging.
CREATE TABLE IF NOT EXISTS attempt (
    id              INTEGER PRIMARY KEY,
    problem_id      TEXT NOT NULL,
    language        TEXT NOT NULL,
    mode            TEXT NOT NULL,              -- 'lc' | 'oa'
    verdict         TEXT NOT NULL,              -- AC | WA | TLE | MLE | RE | CE
    passed          INTEGER NOT NULL DEFAULT 0,
    total           INTEGER NOT NULL DEFAULT 0,
    duration_s      REAL,                       -- wall time the user spent, when known
    runtime_ms      INTEGER,                    -- slowest test's execution time
    source_code     TEXT,
    compile_output  TEXT,
    first_fail_idx  INTEGER,                    -- 0-based index of first failing test, NULL if AC
    stdout_snippet  TEXT,
    stderr_snippet  TEXT,
    created_at      TEXT NOT NULL,
    imported_from   TEXT                        -- 'history.json' for pre-v2 rows (no code)
);
CREATE INDEX IF NOT EXISTS ix_attempt_problem ON attempt (problem_id, created_at);
CREATE INDEX IF NOT EXISTS ix_attempt_verdict ON attempt (verdict);
CREATE INDEX IF NOT EXISTS ix_attempt_created ON attempt (created_at);

-- ---------------------------------------------------------------- runs (one row per RUN)
-- v1 did not record these at all. Pruned to the most recent N per problem.
CREATE TABLE IF NOT EXISTS run (
    id           INTEGER PRIMARY KEY,
    problem_id   TEXT NOT NULL,
    language     TEXT NOT NULL,
    source_code  TEXT,
    stdin        TEXT,
    stdout       TEXT,
    stderr       TEXT,
    exit_code    INTEGER,
    signal       INTEGER,
    runtime_ms   INTEGER,
    verdict      TEXT,                          -- OK | TLE | MLE | RE | CE
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_run_problem ON run (problem_id, created_at);

-- ---------------------------------------------------------------- drafts (live autosave)
-- Replaces browser localStorage, which was per-origin (so a port change stranded it),
-- unversioned, and one hard-refresh away from loss.
CREATE TABLE IF NOT EXISTS draft (
    problem_id   TEXT NOT NULL,
    language     TEXT NOT NULL,
    source_code  TEXT NOT NULL DEFAULT '',
    cursor_pos   INTEGER,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (problem_id, language)
);

-- ---------------------------------------------------------------- draft snapshots (time travel)
-- Lets you scrub back through half-written code. Written on a timer and before any
-- destructive action (submit / reset / language switch).
CREATE TABLE IF NOT EXISTS draft_snapshot (
    id           INTEGER PRIMARY KEY,
    problem_id   TEXT NOT NULL,
    language     TEXT NOT NULL,
    source_code  TEXT NOT NULL,
    reason       TEXT NOT NULL,                 -- periodic | pre-submit | pre-reset | pre-switch | rescued
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_snapshot_problem ON draft_snapshot (problem_id, language, created_at);

-- ---------------------------------------------------------------- OA sessions
-- v1 recorded duration_s as NULL on every row; the frontend never sent it.
CREATE TABLE IF NOT EXISTS oa_session (
    id          INTEGER PRIMARY KEY,
    problem_id  TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    duration_s  REAL,
    result      TEXT,                           -- final verdict, or NULL if abandoned
    abandoned   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_session_problem ON oa_session (problem_id, started_at);

-- ---------------------------------------------------------------- personal annotations
CREATE TABLE IF NOT EXISTS note (
    problem_id TEXT PRIMARY KEY,
    body_md    TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flag (
    problem_id   TEXT PRIMARY KEY,
    starred      INTEGER NOT NULL DEFAULT 0,
    revisit      INTEGER NOT NULL DEFAULT 0,
    confidence   INTEGER,                       -- 1..5, self-rated
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS setting (
    key   TEXT PRIMARY KEY,
    value TEXT
);
