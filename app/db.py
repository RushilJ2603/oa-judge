"""SQLite connection handling + migration runner for OA Judge v2.

One file (app/data/judge.db) holds everything personal: attempts, runs, drafts, snapshots,
notes, flags, settings. It is gitignored and never leaves the machine.

Design notes
------------
* **Per-thread connections.** Flask serves threaded and sqlite3 objects are not shareable
  across threads, so each thread gets its own connection out of a threading.local.
* **WAL where possible.** WAL gives concurrent readers during a write, which matters because
  a judging run holds a connection while compiling. It is unavailable on some network/mounted
  filesystems, so a failure to enable it falls back to the default journal rather than
  crashing (a friend running from a network share must still work).
* **Portability.** See the contract at the top of migrations/001_init.sql. Queries here and in
  store.py stay standard SQL so Phase 6 can point at Postgres with a new driver, not a rewrite.
"""
import os
import sqlite3
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
DB_PATH = os.environ.get("OAJ_DB") or os.path.join(DATA_DIR, "judge.db")
MIGRATIONS_DIR = os.path.join(HERE, "migrations")

_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def _configure(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass  # unsupported filesystem; the default rollback journal is correct, just slower
    # Wait rather than fail if another thread holds the write lock mid-compile.
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")


def connect() -> sqlite3.Connection:
    """The calling thread's connection, creating and migrating the database on first use."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        _configure(conn)
        _local.conn = conn
    init()
    return conn


def close() -> None:
    """Release this thread's connection (tests and shutdown)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


# ------------------------------------------------------------------ migrations
def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER PRIMARY KEY,"
        " applied_at TEXT NOT NULL)"
    )
    conn.commit()
    return {r["version"] for r in conn.execute("SELECT version FROM schema_version")}


def _migration_files() -> list[tuple[int, str]]:
    """[(version, path)] sorted by version, from files named NNN_description.sql."""
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    out = []
    for name in os.listdir(MIGRATIONS_DIR):
        if not name.endswith(".sql"):
            continue
        head = name.split("_", 1)[0]
        if head.isdigit():
            out.append((int(head), os.path.join(MIGRATIONS_DIR, name)))
    return sorted(out)


def init() -> None:
    """Apply any migrations not yet recorded. Idempotent; safe to call on every request."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        conn = _local.conn
        applied = _applied_versions(conn)
        for version, path in _migration_files():
            if version in applied:
                continue
            with open(path, encoding="utf-8") as f:
                sql = f.read()
            # Each migration is one transaction: it fully applies or not at all.
            try:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at)"
                    " VALUES (?, datetime('now'))",
                    (version,),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        _initialized = True


def reset_for_tests() -> None:
    """Drop the cached init flag so a test can point OAJ_DB elsewhere and re-migrate."""
    global _initialized
    close()
    _initialized = False
