#!/usr/bin/env python3
"""Phase 1 — import v1 data into the v2 SQLite database.

Two sources, both optional:

  app/data/history.json          v1 attempt log (metadata only; v1 never stored the code)
  app/data/rescued_drafts.json   localStorage recovered by rescue_drafts.py, keyed by origin

Idempotent: re-running does not duplicate. Attempts are matched on
(problem_id, created_at, verdict); drafts keep whichever copy is longest and snapshot
deduplicates identical content.

    python3 import_v1_data.py            # import
    python3 import_v1_data.py --dry-run  # report only, write nothing
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "app"))

import db     # noqa: E402
import store  # noqa: E402

HISTORY_JSON = os.path.join(HERE, "app", "data", "history.json")
RESCUED_JSON = os.path.join(HERE, "app", "data", "rescued_drafts.json")

# localStorage keys that are settings, not code.
NON_DRAFT_KEYS = {"theme"}


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  !! could not read {os.path.basename(path)}: {e}")
        return None


def import_history(dry_run=False) -> tuple[int, int]:
    rows = _load_json(HISTORY_JSON)
    if not rows:
        print("history.json: absent or empty — nothing to import")
        return 0, 0

    conn = db.connect()
    existing = {(r["problem_id"], r["created_at"], r["verdict"])
                for r in conn.execute(
                    "SELECT problem_id, created_at, verdict FROM attempt")}

    added = skipped = 0
    for r in rows:
        # v1 wrote naive local-time strings; keep them verbatim so the ordering you
        # remember is preserved. New rows are UTC-aware — mixed, but monotonic per era.
        created = r.get("timestamp") or ""
        key = (r.get("problem_id"), created, r.get("verdict"))
        if key in existing:
            skipped += 1
            continue
        if not dry_run:
            store.record_attempt(
                problem_id=r.get("problem_id"),
                language=r.get("language") or "cpp",
                mode=r.get("mode") or "lc",
                verdict=r.get("verdict") or "WA",
                passed=r.get("passed") or 0,
                total=r.get("total") or 0,
                duration_s=r.get("duration_s"),
                source_code=None,          # v1 genuinely did not keep it
                imported_from="history.json",
                created_at=created)
        existing.add(key)
        added += 1
    print(f"history.json: {added} attempt(s) imported, {skipped} already present")
    return added, skipped


def import_rescued_drafts(dry_run=False) -> tuple[int, int]:
    data = _load_json(RESCUED_JSON)
    if not data:
        print("rescued_drafts.json: absent — run rescue_drafts.py in the browser first")
        return 0, 0

    # Collapse every origin into one map, keeping the longest version of each key.
    # A short value is nearly always a stale or reset draft; the long one is real work.
    best: dict[str, tuple[str, str]] = {}   # key -> (value, origin)
    for origin, items in data.items():
        for k, v in (items or {}).items():
            if k in NON_DRAFT_KEYS or v is None:
                continue
            prev = best.get(k)
            if prev is None or len(v) > len(prev[0]):
                best[k] = (v, origin)

    drafts = snaps = 0
    for key, (code, origin) in sorted(best.items()):
        if ":" not in key:
            print(f"  ? skipping unrecognised key {key!r}")
            continue
        problem_id, lang = key.rsplit(":", 1)
        if not code.strip():
            continue
        if not dry_run:
            existing = store.get_draft(problem_id, lang)
            # Never let an import shrink a draft that is already in the DB.
            if existing is None or len(code) > len(existing["source_code"] or ""):
                store.save_draft(problem_id, lang, code)
                drafts += 1
            if store.snapshot_draft(problem_id, lang, code, reason="rescued") is not None:
                snaps += 1
        else:
            drafts += 1
        print(f"  {problem_id} [{lang}] {len(code):>6} chars  (from {origin})")

    print(f"rescued_drafts.json: {drafts} draft(s), {snaps} snapshot(s)")
    return drafts, snaps


def main():
    dry = "--dry-run" in sys.argv
    if dry:
        print("DRY RUN — nothing will be written\n")
    db.connect()
    print(f"database: {db.DB_PATH}\n")
    import_history(dry)
    print()
    import_rescued_drafts(dry)
    if not dry:
        s = store.stats()
        print(f"\nnow in DB: {s['total_attempts']} attempts across "
              f"{s['problems_attempted']} problems, {s['problems_solved']} solved, "
              f"{s['drafts']} drafts, {s['snapshots']} snapshots")


if __name__ == "__main__":
    main()
