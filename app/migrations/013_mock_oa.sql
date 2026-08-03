-- 013_mock_oa — timed multi-problem mock OA papers.
--
-- A mock OA is a SET of problems under one clock, which is the thing the judge could not express
-- before: `oa_session` is per-problem and its timer is client-side, so a reload restarted it and
-- nothing tied three questions together.
--
-- Two decisions worth stating:
--   * `ends_at` is written ONCE, at start, by the server. The countdown the browser draws is a
--     rendering of that value — closing the tab, reloading, or moving to another device cannot buy
--     more time, and the server can always settle "was this submission inside the window?".
--   * `problems_json` freezes the paper at start. Curated sets could otherwise change under a
--     running attempt when the file is edited, and a random paper has to be reproducible in the
--     report months later.
--
-- Per-problem results are NOT stored here. They are derived from `attempt` rows inside
-- [started_at, ended_at] — one source of truth for "did you solve it", already written by the
-- existing submit path, so a mock OA cannot disagree with the rest of the app.
CREATE TABLE IF NOT EXISTS mock_oa_attempt (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL DEFAULT 1,
    set_id        TEXT NOT NULL,               -- curated set id, or 'random' for a generated paper
    title         TEXT NOT NULL,
    minutes       INTEGER NOT NULL,
    problems_json TEXT NOT NULL,               -- ordered problem ids, frozen at start
    started_at    TEXT NOT NULL,
    ends_at       TEXT NOT NULL,               -- server-authoritative deadline
    ended_at      TEXT,                        -- when it was finished/expired/abandoned
    status        TEXT NOT NULL DEFAULT 'running',   -- running | finished | abandoned
    score_json    TEXT                         -- frozen result snapshot, written at finish
);
CREATE INDEX IF NOT EXISTS ix_mock_user    ON mock_oa_attempt (user_id, started_at);
CREATE INDEX IF NOT EXISTS ix_mock_running ON mock_oa_attempt (user_id, status);
