# OA Judge — single image used both as the web app and as the per-run execution sandbox.
# It carries g++ (C++17) and python3, so the same image can compile/run submissions.
FROM python:3.12-slim

# Toolchain for judging + git (for the problem bank + in-app Sync) + coreutils `timeout` (in base).
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask waitress

WORKDIR /app
COPY app/ /app/app/
COPY verify_all.py make_hidden.py /app/

# Bake the shared problem bank into the image so a hosted instance is self-contained. It's a
# public repo, so no auth is needed; override the URL/ref at build time if you fork it. The in-app
# Sync button still `git pull`s newer problems at runtime.
ARG OA_PROBLEMS_REPO=https://github.com/RushilJ2603/oa-problems.git
ARG OA_PROBLEMS_REF=main
# Cache-bust the clone whenever the bank has a new commit: ADD of this URL re-fetches on each build
# and its content (the latest commit sha) changes exactly when there are new problems, so Docker
# re-runs the clone below only then. Without this, the clone layer would cache and a redeploy would
# ship a stale bank. (The in-app Sync button still pulls newer problems at runtime regardless.)
ADD https://api.github.com/repos/RushilJ2603/oa-problems/commits/${OA_PROBLEMS_REF} /tmp/bank-version.json
RUN git clone --depth 1 --branch "${OA_PROBLEMS_REF}" "${OA_PROBLEMS_REPO}" /problems || \
    (echo "WARNING: could not clone the problem bank; starting empty" && mkdir -p /problems)

# Non-root web user. Untrusted code, under the docker backend, runs in its own throwaway container
# as 'nobody'; on Fly (no Docker socket) it runs here as this unprivileged user inside the
# per-app Firecracker microVM, which is itself the isolation boundary.
RUN useradd -m -u 10001 judge \
    && mkdir -p /app/app/data /data \
    && chown -R judge /app /data /problems
USER judge

ENV OAJ_HOST=0.0.0.0 \
    OAJ_PORT=5137 \
    OAJ_PROBLEMS_DIR=/problems \
    OAJ_DB=/data/judge.db \
    OAJ_EXEC_BACKEND=local \
    PYTHONUNBUFFERED=1

EXPOSE 5137
# waitress is present, so server.py serves through it automatically.
CMD ["python3", "app/server.py"]
