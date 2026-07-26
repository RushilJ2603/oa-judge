-- 007_sheet_code — the per-user scratchpad attached to a sheet problem. Lets a user draft their
-- solution inside OA Judge and copy it straight into the external judge's paste box, so the sheet
-- links themselves stay untouched. One row per (user, item), scoped by user_id exactly like
-- sheet_progress. Portability contract from 001 holds: TEXT / INTEGER only, ISO-8601 UTC timestamps.
CREATE TABLE IF NOT EXISTS sheet_code (
    user_id    INTEGER NOT NULL,
    item_id    TEXT NOT NULL,
    lang       TEXT NOT NULL DEFAULT 'cpp',
    code       TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);
