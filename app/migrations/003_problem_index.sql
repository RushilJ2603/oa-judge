-- 003_problem_index — columns + indexes for source-grouped search at scale (thousands of problems).
--
-- problem_index (created in 001) is a rebuilt-from-disk cache. Add the fields the new sidebar
-- filters on. It's a cache, so adding columns + repopulating is safe; no data migration needed.

ALTER TABLE problem_index ADD COLUMN source TEXT NOT NULL DEFAULT 'gyan';
ALTER TABLE problem_index ADD COLUMN topic  TEXT NOT NULL DEFAULT '';
ALTER TABLE problem_index ADD COLUMN title_lc TEXT NOT NULL DEFAULT '';   -- lowercased for search

CREATE INDEX IF NOT EXISTS ix_pidx_source     ON problem_index (source);
CREATE INDEX IF NOT EXISTS ix_pidx_company    ON problem_index (company);
CREATE INDEX IF NOT EXISTS ix_pidx_difficulty ON problem_index (difficulty);
CREATE INDEX IF NOT EXISTS ix_pidx_title      ON problem_index (title_lc);
