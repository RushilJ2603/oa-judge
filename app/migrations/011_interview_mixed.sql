-- Mixed interviews: one session that walks several rubrics, the way a real loop moves from CS
-- fundamentals to a DSA discussion to a design question without starting a new conversation.
--
-- Stored as a plan of segments on the session rather than a new table: a segment is just
-- {rubric_id, phases[]}, and the session tracks which one it is on. That keeps every existing
-- single-rubric session valid (plan_json NULL => the old behaviour) and means scoring, checkoffs
-- and the dossier need no changes — they are already keyed by rubric_id + point_id.
ALTER TABLE interview_session ADD COLUMN plan_json TEXT;      -- [{"rubric_id":..,"phases":[..]}, ..]
ALTER TABLE interview_session ADD COLUMN segment_idx INTEGER NOT NULL DEFAULT 0;
