-- 004_presence — best-effort "who's online" for the hosted deployment.
--
-- `last_seen` is bumped from the user's real API traffic (loading problems, submitting, autosaving) —
-- there is NO background heartbeat. That's deliberate: a recurring heartbeat would keep the
-- scale-to-zero machine awake and cost money. So presence is free and never wakes the machine on its
-- own; "online" simply means "made a request in the last few minutes". Portable TEXT ISO-8601 UTC,
-- consistent with every other timestamp in the schema.
ALTER TABLE "user" ADD COLUMN last_seen TEXT;

CREATE INDEX IF NOT EXISTS ix_user_last_seen ON "user" (last_seen);
