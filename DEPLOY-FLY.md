# Deploy OA Judge to Fly.io (shared URL, GitHub login)

End state: a URL like `https://oa-judge.fly.dev` that your friends open, sign into with GitHub,
and use — each seeing only their own attempts, drafts, and stats, over one shared problem bank.
No installs on their side.

Time: ~15 minutes. You need a Fly.io account and a GitHub account.

---

## 1. Install flyctl and log in

```bash
curl -L https://fly.io/install.sh | sh      # then add the printed line to your PATH
fly auth login
```

## 2. Create the app + a volume for the database

From the `oa-judge` repo root:

```bash
fly launch --no-deploy --copy-config --name YOUR-APP-NAME --region iad
```
- Say **no** to Postgres/Redis (the app uses SQLite on a volume).
- Edit `fly.toml`: set `app = "YOUR-APP-NAME"` (must be globally unique) and your region.

Create the persistent volume the DB lives on:

```bash
fly volumes create oaj_data --region iad --size 1
```

Your URL will be `https://YOUR-APP-NAME.fly.dev`. Note it — you need it next.

## 3. Create a GitHub OAuth app

GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**:

- **Application name:** OA Judge (anything)
- **Homepage URL:** `https://YOUR-APP-NAME.fly.dev`
- **Authorization callback URL:** `https://YOUR-APP-NAME.fly.dev/auth/callback`  ← must match exactly

Create it, then **Generate a new client secret**. Copy the **Client ID** and **Client secret**.

## 4. Set the secrets on Fly

```bash
fly secrets set \
  OAJ_GITHUB_CLIENT_ID=xxxxxxxxxxxx \
  OAJ_GITHUB_CLIENT_SECRET=yyyyyyyyyyyyyyyy \
  OAJ_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
  OAJ_BASE_URL="https://YOUR-APP-NAME.fly.dev"
```

`OAJ_SECRET_KEY` signs the login cookie — keep it stable, or everyone gets logged out on each
change. Setting these is also what flips the app into multi-user mode; without them it would run
single-user with no login.

## 5. Deploy

```bash
fly deploy
```

Fly builds the image (cloning the public problem bank into it), runs it, and gives you HTTPS.
Open `https://YOUR-APP-NAME.fly.dev` → **Sign in with GitHub** → you're in. Share the URL.

---

## Operating it

- **New problems:** add via the in-app **Add** button (which verifies before publishing) or push to
  the `oa-problems` repo, then hit **Sync** in the app. A redeploy also picks up the latest bank.
- **Logs:** `fly logs`. **Shell:** `fly ssh console`. **Scale/stop:** `fly scale count 0|1`.
- **Backups:** the DB is at `/data/judge.db` on the `oaj_data` volume. Snapshot with
  `fly volumes snapshots create <vol-id>`, or `fly ssh console` + copy it out.

## Security notes (important)

- On Fly each app runs in its own **Firecracker microVM** — that VM is the isolation boundary for
  submitted code, which runs as an unprivileged user under CPU/memory/output limits. This is a
  sound model for a friend group.
- The one residual: `OAJ_EXEC_BACKEND=local` means submitted code shares the VM's network, so it
  can make outbound connections. For a friend group that's fine. If you ever open this to strangers,
  move to a VPS with `OAJ_EXEC_BACKEND=docker` (per-run `--network none` containers — see DEPLOY.md).
- Only people who sign in with GitHub can use it, but by default **anyone** with a GitHub account
  can. **Lock it to your group** with an allow-list of GitHub usernames:
  ```bash
  fly secrets set OAJ_GITHUB_ALLOWED="yourlogin,friend1,friend2"
  ```
  Anyone not listed is refused at sign-in. Leave it unset to keep it open.

## Costs

The `shared-cpu-1x` / 512 MB VM with scale-to-zero (`min_machines_running = 0`) fits comfortably in
Fly's free allowance for a small group; the 1 GB volume is free. It sleeps when idle and wakes on
the next request (a second of cold start).
