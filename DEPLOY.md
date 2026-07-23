# Deploying OA Judge

The app is a Flask server that **compiles and runs submitted code**. That single fact drives every
deployment decision: the moment other people can submit, you are running untrusted code on your
box. Read the security model before exposing it beyond your own machine.

---

## Threat model — read this first

| Who submits code | Recommended model | Why |
|---|---|---|
| Just you, locally | `local` backend, no container | It's your own code; rlimits stop runaway loops. This is the default and needs nothing here. |
| A **trusted** friend group | one hardened container, `local` backend | The container is the blast radius. Friends' code shares the container's network but can't touch the host. Simplest real deploy. |
| **Untrusted** / public | `docker` backend (container-per-run) | Each submission runs in an ephemeral, **network-less**, read-only, non-root, resource-capped container. The only model safe against hostile code. |

Do **not** put the `local`-backend container on the public internet. A shared network namespace
means a submission can make outbound connections, scan your LAN, or exfiltrate. That's fine among
friends who trust each other; it is not fine for strangers.

---

## Option A — single hardened container (trusted friends)

```bash
git clone <oa-judge-url> && cd oa-judge
git clone <oa-problems-url> problems          # the shared bank, mounted read-only
docker compose up -d --build                  # serves on http://<host>:5137
```

`docker-compose.yml` already applies `no-new-privileges`, a PID cap, and a memory cap, and keeps
your database on a named volume. Put it behind a reverse proxy (Caddy/nginx) for TLS.

What this gives you: a friend's infinite loop or fork bomb is contained and killed; a crash can't
corrupt the host; the DB survives restarts. What it does **not** give you: protection from
deliberately hostile code, which shares the container's network.

## Option B — container-per-run (untrusted code)

Set the backend to `docker` and mount the Docker socket so the app can spawn sandbox containers:

```yaml
# in docker-compose.yml
environment:
  OAJ_EXEC_BACKEND: "docker"
  OAJ_DOCKER_IMAGE: "oa-judge:latest"
volumes:
  - /var/run/docker.sock:/var/run/docker.sock   # uncomment this line
```

Every compile and every run then executes in a throwaway container with:

```
--network none            no network, at all
--read-only               immutable root fs (+ a capped tmpfs scratch dir)
--cap-drop ALL            no Linux capabilities
--security-opt no-new-privileges
--user 65534:65534        runs as 'nobody'
--pids-limit / --memory / --cpus   hard resource ceilings
--rm                      deleted the instant it exits
```

**The trade-off:** the app container can spawn host containers via the Docker socket, which is a
privileged capability — if the *app* is compromised, that's a host-level foothold. For a stricter
setup, run the app behind an authenticated proxy (Option C) and/or use a rootless Docker or a
dedicated runner host. gVisor (`--runtime=runsc`) adds a syscall-level barrier if you want more.

## Option C — a hosting platform

The image runs anywhere that runs a container:

- **Fly.io / Railway / Render:** push the image, attach a volume for `/data`, set the `OAJ_*` env
  vars. These platforms don't give you a Docker socket, so use the `local` backend and keep access
  behind login (below) — treat it as "trusted users with accounts", not "open to the world".
- **A small VPS ($5/mo):** full control; Option B (container-per-run) works here. This is the only
  option that is genuinely safe for untrusted submissions.

---

## Database: SQLite → Postgres

For a single instance, SQLite on a persistent volume (the default, `/data/judge.db`) is entirely
sufficient — WAL handles the concurrency a friend group generates. Move to Postgres only when you
run multiple app instances or want managed backups. The schema was written Postgres-portable on
purpose (`app/migrations/001_init.sql`): `INTEGER PRIMARY KEY` becomes
`BIGINT GENERATED ALWAYS AS IDENTITY`, and the upserts already use standard
`ON CONFLICT ... DO UPDATE`. Porting is a driver swap in `app/db.py`, not a rewrite.

## Multi-user login (when you need per-person data)

The current build stores one person's attempts/drafts/notes per database — perfect for local use
and fine for a friend group where everyone runs their own copy and shares only the problem bank.
If you host **one** instance for several people and want each to see only their own history, add:

1. GitHub OAuth (everyone already has GitHub) → a `user` row.
2. A `user_id` column on `attempt`, `run`, `draft`, `draft_snapshot`, `oa_session`, `note`, `flag`
   (a numbered migration; the schema is already additive-friendly).
3. Scope every `store.py` query by the logged-in `user_id`.

This is the one piece intentionally left for when it's actually needed — a friend group sharing
only the question bank doesn't need it, and it's a clean additive migration when they do.

---

## Sanity checklist before exposing it

- [ ] Untrusted submitters? → `docker` backend on a VPS, **not** the `local`-backend container.
- [ ] TLS via a reverse proxy.
- [ ] Access control (at minimum HTTP basic auth on the proxy; OAuth if multi-user).
- [ ] `/data` on a backed-up volume.
- [ ] Resource caps sized to the host (`pids_limit`, `mem_limit`, `OAJ_DOCKER_CPUS`).
- [ ] The problem bank mounted **read-only**.
