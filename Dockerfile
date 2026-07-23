# OA Judge — single image used both as the web app and as the per-run execution sandbox.
# It carries g++ (C++17) and python3, so the same image can compile/run submissions.
FROM python:3.12-slim

# Toolchain for judging + coreutils `timeout` (already in the base) + git for the problem bank.
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask waitress

# App code. The problems bank is mounted/cloned at runtime (a separate repo), not baked in.
WORKDIR /app
COPY app/ /app/app/
COPY verify_all.py make_hidden.py /app/
# A non-root user for the web process. Untrusted code, under the docker backend, runs in its own
# throwaway container as 'nobody' — never in this one.
RUN useradd -m -u 10001 judge && mkdir -p /app/app/data && chown -R judge /app
USER judge

ENV OAJ_HOST=0.0.0.0 \
    OAJ_PORT=5137 \
    OAJ_PROBLEMS_DIR=/problems \
    OAJ_DB=/data/judge.db \
    PYTHONUNBUFFERED=1

EXPOSE 5137
# waitress is present, so server.py serves through it automatically.
CMD ["python3", "app/server.py"]
