"""Load problem packages from the problems bank (a separate oa-problems checkout)."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # oa-judge/
sys.path.insert(0, os.path.dirname(HERE))              # app/ on the path for config
import config  # noqa: E402

# The question bank lives in its own repo (oa-problems) cloned into oa-judge/problems/.
# Resolved via app/config.py so hosting can point elsewhere without editing this file.
PROBLEMS_DIR = config.PROBLEMS_DIR

STUB_FILE = {"cpp": "stub.cpp", "py": "stub.py"}
REFERENCE_FILE = {"cpp": "reference.cpp", "py": "reference.py"}
DEFAULT_LIMITS = {"time_ms": 2000, "memory_mb": 256}


def _read(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return None


def list_ids() -> list[str]:
    if not os.path.isdir(PROBLEMS_DIR):
        return []
    ids = []
    for name in sorted(os.listdir(PROBLEMS_DIR)):
        d = os.path.join(PROBLEMS_DIR, name)
        if os.path.isfile(os.path.join(d, "problem.json")):
            ids.append(name)
    return ids


def _load_tests(pdir, group) -> list[dict]:
    tdir = os.path.join(pdir, "tests", group)
    if not os.path.isdir(tdir):
        return []
    tests = []
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".in"):
            continue
        stem = fn[:-3]
        inp = _read(os.path.join(tdir, fn))
        out = _read(os.path.join(tdir, stem + ".out"))
        if inp is None or out is None:
            continue
        tests.append({"index": len(tests) + 1, "input": inp, "output": out})
    return tests


def load(pid: str) -> dict | None:
    pdir = os.path.join(PROBLEMS_DIR, pid)
    meta_raw = _read(os.path.join(pdir, "problem.json"))
    if meta_raw is None:
        return None
    meta = json.loads(meta_raw)
    meta.setdefault("limits", dict(DEFAULT_LIMITS))
    for k, v in DEFAULT_LIMITS.items():
        meta["limits"].setdefault(k, v)
    meta.setdefault("compare", "tokens")
    meta.setdefault("languages", [])
    meta.setdefault("links", [])
    meta.setdefault("runnable", True)

    stubs = {lang: _read(os.path.join(pdir, STUB_FILE[lang])) or ""
             for lang in meta["languages"]}
    references = {lang: _read(os.path.join(pdir, REFERENCE_FILE[lang]))
                  for lang in meta["languages"]}
    references = {k: v for k, v in references.items() if v is not None}

    return {
        "dir": pdir,
        "meta": meta,
        "statement_md": _read(os.path.join(pdir, "statement.md")) or "",
        "editorial_md": _read(os.path.join(pdir, "editorial.md")) or "",
        "stubs": stubs,
        "references": references,
        "generator_path": (os.path.join(pdir, "generator.py")
                           if os.path.exists(os.path.join(pdir, "generator.py")) else None),
        "samples": _load_tests(pdir, "sample"),
        "hidden": _load_tests(pdir, "hidden"),
    }


def meta_only(pid: str) -> dict | None:
    """Parse just problem.json — no test files. Cheap enough to run over thousands of problems
    for indexing. Returns the normalized metadata the index/search layer needs."""
    meta_raw = _read(os.path.join(PROBLEMS_DIR, pid, "problem.json"))
    if meta_raw is None:
        return None
    try:
        m = json.loads(meta_raw)
    except json.JSONDecodeError:
        return None
    return {
        "id": m.get("id", pid),
        "title": m.get("title", pid),
        "source": (m.get("source") or "gyan"),
        "topic": (m.get("topic") or ""),
        "company": (m.get("company") or ""),
        "difficulty": (m.get("difficulty") or ""),
        "tags": m.get("tags", []),
        "languages": m.get("languages", []),
        "runnable": bool(m.get("runnable", True)),
    }


def all_meta() -> list[dict]:
    """Light metadata for every problem on disk — the input to (re)building the search index."""
    out = []
    for pid in list_ids():
        m = meta_only(pid)
        if m:
            out.append(m)
    return out


def summary(pid: str) -> dict | None:
    p = load(pid)
    if p is None:
        return None
    m = p["meta"]
    return {
        "id": m["id"], "title": m.get("title", m["id"]),
        "company": m.get("company", ""), "difficulty": m.get("difficulty", ""),
        "tags": m.get("tags", []), "languages": m["languages"],
        "runnable": m["runnable"], "links": m["links"],
    }
