-- Mock interview: sessions, transcript, and the persistent candidate dossier.
-- Portable SQL per 001_init.sql contract. Every personal table is scoped by user_id so friends
-- sharing the host never see each other's transcripts, evidence, or dossier.
--
-- The dossier (skill / behavior / candidate_fact) is the thing a chat model cannot have: it is what
-- makes the interviewer open with "last time you couldn't explain cache stampede" instead of asking
-- you to re-establish who you are on every single session.

-- ---------------------------------------------------------------- a single interview
CREATE TABLE IF NOT EXISTS interview_session (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL,
    kind          TEXT    NOT NULL,            -- HLD | LLD | CONCEPT | CP | DSA
    rubric_id     TEXT    NOT NULL,            -- e.g. hq01_url_shortener
    problem_id    TEXT,                        -- set for DSA rounds judged against the bank
    started_at    TEXT    NOT NULL,
    ended_at      TEXT,
    status        TEXT    NOT NULL DEFAULT 'active',   -- active | done | abandoned
    current_phase TEXT,
    hint_tier     INTEGER NOT NULL DEFAULT 0,  -- highest hint tier RELEASED so far this phase
    stuck_signals INTEGER NOT NULL DEFAULT 0,  -- app-counted; gates hint escalation
    score_json    TEXT,                        -- per-phase scores, computed by the app
    summary       TEXT                         -- compact recap written into the session ledger
);
CREATE INDEX IF NOT EXISTS ix_isession_user ON interview_session (user_id, started_at);

-- ---------------------------------------------------------------- the transcript
-- Full fidelity is kept here; the assembler sends only the last few turns verbatim plus a rolling
-- summary, so a 45-minute interview costs the same per turn as a 5-minute one.
CREATE TABLE IF NOT EXISTS interview_turn (
    id         INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    idx        INTEGER NOT NULL,               -- 0-based order within the session
    role       TEXT    NOT NULL,               -- interviewer | candidate | system
    phase      TEXT,
    content    TEXT    NOT NULL,
    hint_tier  INTEGER NOT NULL DEFAULT 0,     -- tier in force when this turn was produced
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_iturn_session ON interview_turn (session_id, idx);

-- ---------------------------------------------------------------- rubric evidence
-- One row per rubric point the interviewer ruled on. This is the raw signal the skill model is
-- built from, and the reason a score can be recomputed/audited later without re-running the model.
CREATE TABLE IF NOT EXISTS interview_checkoff (
    session_id TEXT    NOT NULL,
    user_id    INTEGER NOT NULL,
    rubric_id  TEXT    NOT NULL,
    phase      TEXT    NOT NULL,
    point_id   TEXT    NOT NULL,               -- e.g. est2 — the id the model returns, never prose
    status     TEXT    NOT NULL,               -- hit | partial | missed
    evidence   TEXT,                           -- quoted from the candidate's own answer
    created_at TEXT    NOT NULL,
    PRIMARY KEY (session_id, point_id)
);
CREATE INDEX IF NOT EXISTS ix_icheck_user ON interview_checkoff (user_id, rubric_id, point_id);

-- ---------------------------------------------------------------- dossier: skill model
-- concept_key is "<rubric_id>:<point_id>" for interview evidence, or a bare concept slug when the
-- signal comes from elsewhere (judge verdicts, notes drills). mastery is a decayed hit-rate in
-- [0,1]; question selection targets the band where the candidate is ~60-70% successful.
CREATE TABLE IF NOT EXISTS skill (
    user_id       INTEGER NOT NULL,
    concept_key   TEXT    NOT NULL,
    label         TEXT    NOT NULL DEFAULT '', -- human-readable, for "you missed X" phrasing
    mastery       REAL    NOT NULL DEFAULT 0,
    times_tested  INTEGER NOT NULL DEFAULT 0,
    times_hit     INTEGER NOT NULL DEFAULT 0,
    last_tested_at TEXT,
    last_evidence TEXT,
    PRIMARY KEY (user_id, concept_key)
);
CREATE INDEX IF NOT EXISTS ix_skill_weak ON skill (user_id, mastery);

-- ---------------------------------------------------------------- dossier: behavioural profile
-- HOW the candidate interviews, which is half the real score and needs many sessions to see.
-- trait ∈ clarifies_first | thinks_aloud | states_complexity | hint_dependency | pacing | verbosity
CREATE TABLE IF NOT EXISTS behavior (
    user_id      INTEGER NOT NULL,
    trait        TEXT    NOT NULL,
    value        REAL    NOT NULL DEFAULT 0,   -- running mean in [0,1]
    observations INTEGER NOT NULL DEFAULT 0,
    last_evidence TEXT,
    updated_at   TEXT    NOT NULL,
    PRIMARY KEY (user_id, trait)
);

-- ---------------------------------------------------------------- dossier: standing facts
-- Set once, referenced forever: resume highlights, target companies, timeline, current CF rating.
-- This is the context you would otherwise retype into a chat window every session.
CREATE TABLE IF NOT EXISTS candidate_fact (
    user_id    INTEGER NOT NULL,
    key        TEXT    NOT NULL,
    value      TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    PRIMARY KEY (user_id, key)
);

-- ---------------------------------------------------------------- worker queue (host mode)
-- The local agy worker leases jobs outbound; it never accepts inbound connections. Session state
-- lives here, not in the worker, so a worker that dies mid-interview (WSL down, laptop asleep)
-- loses nothing — the turn is simply re-leased.
CREATE TABLE IF NOT EXISTS interview_job (
    id           INTEGER PRIMARY KEY,
    session_id   INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    kind         TEXT    NOT NULL,             -- turn | summarize
    payload_json TEXT    NOT NULL,             -- STRUCTURED data only, never prompt text
    status       TEXT    NOT NULL DEFAULT 'queued',  -- queued | leased | done | failed
    attempts     INTEGER NOT NULL DEFAULT 0,
    lease_until  TEXT,
    result_json  TEXT,
    error        TEXT,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ijob_queue ON interview_job (status, created_at);

-- Worker liveness. The UI derives "Interviewer online" from a recent beat, so the host toggle is
-- simply whether the worker is running — there is no separate flag to drift out of sync.
CREATE TABLE IF NOT EXISTS worker_beat (
    worker_id  TEXT PRIMARY KEY,
    last_seen  TEXT NOT NULL,
    version    TEXT
);
