-- 006_cp_sheets — the CP + System Design "sheets" feature, the per-user checklist that rides them,
-- linked competitive-programming handles, a cached stats snapshot per site, a cached upcoming-contest
-- feed, and the per-user rating goal that powers the deterministic on-track tracker.
--
-- Portability contract from 001 holds: TEXT / INTEGER only, standard SQL, ISO-8601 UTC timestamps.
-- Everything personal is scoped by user_id exactly like attempt/draft/note/flag. No AI, no external
-- state: the tracker is pure arithmetic over data pulled from the linked handles and cached here.

-- Per-user checklist state for a sheet item (a problem or a resource). item_id is the stable id
-- minted in the sheet JSON (e.g. "cp:constructive:cf1003B"). status: 'todo' | 'done' | 'revisit'.
CREATE TABLE IF NOT EXISTS sheet_progress (
    user_id    INTEGER NOT NULL,
    item_id    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'done',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);
CREATE INDEX IF NOT EXISTS ix_sheet_progress_user ON sheet_progress (user_id, status);

-- A user's handle on each competitive-programming site. One row per (user, site).
-- site: 'codeforces' | 'atcoder' | 'leetcode' | 'codechef'.
CREATE TABLE IF NOT EXISTS cp_handle (
    user_id    INTEGER NOT NULL,
    site       TEXT NOT NULL,
    handle     TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, site)
);

-- Cached stats snapshot per (user, site) so we hit the external APIs at most once every few hours
-- and degrade to last-known on failure. payload is an opaque JSON blob shaped by the fetcher.
CREATE TABLE IF NOT EXISTS cp_stats_cache (
    user_id    INTEGER NOT NULL,
    site       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    ok         INTEGER NOT NULL DEFAULT 1,   -- 0 = last refresh failed; serve payload as stale
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (user_id, site)
);

-- Global cache of upcoming contests (shared across all users; refreshed hourly). Wiped + refilled
-- on refresh, so no per-user rows. start_at / end are ISO-8601 UTC.
CREATE TABLE IF NOT EXISTS contest_cache (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    site         TEXT NOT NULL,
    name         TEXT NOT NULL,
    url          TEXT NOT NULL,
    start_at     TEXT NOT NULL,
    duration_min INTEGER,
    fetched_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_contest_start ON contest_cache (start_at);

-- Per-user goal + calibration anchor for the tracker. The target trajectory is the straight line
-- from (start_at, start_rating) to (deadline, target_rating); "on track" compares today's real
-- rating to the point on that line. Defaults encode "Candidate Master by end of May 2027".
CREATE TABLE IF NOT EXISTS cp_goal (
    user_id       INTEGER NOT NULL PRIMARY KEY,
    target_rating INTEGER NOT NULL DEFAULT 1900,
    deadline      TEXT NOT NULL DEFAULT '2027-05-31',
    start_rating  INTEGER,          -- calibration rating; NULL until first sync sets it
    start_at      TEXT,             -- when calibration was taken
    pace_per_day  INTEGER NOT NULL DEFAULT 3,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
