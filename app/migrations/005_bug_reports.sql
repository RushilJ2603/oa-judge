-- 005_bug_reports — one-click "report an issue" so a solver can flag a bad statement, a wrong
-- test, or a typo without leaving the problem. Stored locally in judge.db like everything else;
-- the owner reviews them via GET /api/reports. Portable TEXT ISO-8601 UTC timestamp. user_id is
-- nullable so a report survives even if the reporter is anonymous (AUTH off) or later removed.
CREATE TABLE IF NOT EXISTS bug_report (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id TEXT NOT NULL,
    user_id    INTEGER,
    message    TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_bug_report_problem ON bug_report (problem_id);
