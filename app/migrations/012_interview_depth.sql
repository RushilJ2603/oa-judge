-- Depth of an interview, chosen when it starts.
--
-- 'standard' is the behaviour that already existed: walk the rubric, advance when its core points
-- are met. 'deep' treats the rubric as a FLOOR rather than a ceiling — the interviewer swaps to the
-- __deep companion where one exists, is authorised to ask questions no rubric point names, and does
-- not have to stop the moment the checklist is satisfied.
--
-- Stored per session, not per user: the same person wants a quick pass on one topic and a hard one
-- on another, and a past interview must keep the depth it was actually conducted at so its report
-- and its dossier contribution stay interpretable.
ALTER TABLE interview_session ADD COLUMN depth TEXT NOT NULL DEFAULT 'standard';

-- Phases skipped because the dossier already showed mastery, so the report can say "skipped — you
-- have covered this" instead of scoring them zero and looking like a failure.
ALTER TABLE interview_session ADD COLUMN skipped_json TEXT;
