-- 002_users — multi-user support for the hosted deployment.
--
-- Adds a `user` table and scopes every personal table by user_id. Local single-user installs keep
-- working: a default user (id 1, login 'local') owns all pre-existing rows, and when no OAuth is
-- configured the app runs as that user with no login. Portability contract from 001 still holds
-- (TEXT/INTEGER/REAL, standard SQL); on Postgres the surrogate id becomes IDENTITY.

CREATE TABLE IF NOT EXISTS "user" (
    id          INTEGER PRIMARY KEY,
    github_id   INTEGER UNIQUE,           -- NULL for the implicit local user
    login       TEXT NOT NULL,
    name        TEXT,
    avatar_url  TEXT,
    created_at  TEXT NOT NULL
);

-- The implicit owner of everything that existed before multi-user. github_id NULL so it can never
-- collide with a real GitHub account.
INSERT INTO "user" (id, github_id, login, name, avatar_url, created_at)
SELECT 1, NULL, 'local', 'Local user', NULL, datetime('now')
WHERE NOT EXISTS (SELECT 1 FROM "user" WHERE id = 1);

-- Surrogate-PK tables: just add a nullable column and backfill to the local user.
ALTER TABLE attempt        ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE run            ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE draft_snapshot ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE oa_session     ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS ix_attempt_user  ON attempt (user_id, problem_id, created_at);
CREATE INDEX IF NOT EXISTS ix_run_user      ON run (user_id, problem_id, created_at);
CREATE INDEX IF NOT EXISTS ix_snapshot_user ON draft_snapshot (user_id, problem_id, language, created_at);
CREATE INDEX IF NOT EXISTS ix_session_user  ON oa_session (user_id, problem_id, started_at);

-- Composite-PK tables (draft, note, flag) must be rebuilt: their PK now includes user_id so two
-- users can each have their own draft/note/flag for the same problem.
CREATE TABLE draft_new (
    user_id      INTEGER NOT NULL,
    problem_id   TEXT NOT NULL,
    language     TEXT NOT NULL,
    source_code  TEXT NOT NULL DEFAULT '',
    cursor_pos   INTEGER,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (user_id, problem_id, language)
);
INSERT INTO draft_new (user_id, problem_id, language, source_code, cursor_pos, updated_at)
SELECT 1, problem_id, language, source_code, cursor_pos, updated_at FROM draft;
DROP TABLE draft;
ALTER TABLE draft_new RENAME TO draft;

CREATE TABLE note_new (
    user_id    INTEGER NOT NULL,
    problem_id TEXT NOT NULL,
    body_md    TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, problem_id)
);
INSERT INTO note_new (user_id, problem_id, body_md, updated_at)
SELECT 1, problem_id, body_md, updated_at FROM note;
DROP TABLE note;
ALTER TABLE note_new RENAME TO note;

CREATE TABLE flag_new (
    user_id      INTEGER NOT NULL,
    problem_id   TEXT NOT NULL,
    starred      INTEGER NOT NULL DEFAULT 0,
    revisit      INTEGER NOT NULL DEFAULT 0,
    confidence   INTEGER,
    last_seen_at TEXT,
    PRIMARY KEY (user_id, problem_id)
);
INSERT INTO flag_new (user_id, problem_id, starred, revisit, confidence, last_seen_at)
SELECT 1, problem_id, starred, revisit, confidence, last_seen_at FROM flag;
DROP TABLE flag;
ALTER TABLE flag_new RENAME TO flag;
