-- Problem of the Day solve log: one row per (user, day) when they AC that day's POTD.
-- Streaks are derived from this table (consecutive days). Portable SQL per 001_init.sql contract.
CREATE TABLE IF NOT EXISTS potd_solve (
    user_id    INTEGER NOT NULL,
    day        TEXT    NOT NULL,   -- IST calendar day, YYYY-MM-DD
    problem_id TEXT    NOT NULL,
    solved_at  TEXT    NOT NULL,
    PRIMARY KEY (user_id, day)
);
