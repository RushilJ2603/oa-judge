"""Load the generated rubric corpus from problems/_interview/rubrics/.

Rubrics are static data generated offline and gated by gate_rubric.py, so this module only reads
and caches. Deliberately no generator dependency at runtime: production must never need Grok or agy
installed to serve an interview.
"""
import functools
import json
import os

PROBLEMS_DIR = os.environ.get("OAJ_PROBLEMS_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "problems")
RUBRIC_DIR = os.path.join(PROBLEMS_DIR, "_interview", "rubrics")
RESEARCH_DIR = os.path.join(PROBLEMS_DIR, "_interview", "research")

# Phase order per type. The interview walks these in order; a rubric may omit trailing phases.
PHASE_ORDER = {
    "HLD": ["requirements", "estimation", "api", "data_model", "architecture", "deep_dives", "bottlenecks"],
    "LLD": ["requirements", "entities", "class_design", "implementation", "extensibility", "concurrency"],
    "CONCEPT": ["fundamentals", "mechanics", "tradeoffs", "application"],
    "CP": ["recognition", "approach", "implementation", "complexity", "pitfalls"],
    "FUND": ["fundamentals", "mechanics", "tradeoffs", "application"],
}


def list_ids() -> list[str]:
    if not os.path.isdir(RUBRIC_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(RUBRIC_DIR) if f.endswith(".json"))


@functools.lru_cache(maxsize=256)
def load(rubric_id: str) -> dict | None:
    """Rubrics never change at runtime, so caching them is free correctness-wise."""
    if not rubric_id or "/" in rubric_id or "\\" in rubric_id or rubric_id.startswith("."):
        return None                                   # path-traversal guard: ids are flat slugs
    p = os.path.join(RUBRIC_DIR, rubric_id + ".json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def summaries() -> list[dict]:
    """Light metadata for pickers ("choose an interview")."""
    out = []
    for rid in list_ids():
        d = load(rid)
        if d:
            out.append({"id": rid, "title": d.get("title", rid), "type": d.get("type", ""),
                        "difficulty": d.get("difficulty", ""), "relevance": d.get("relevance", ""),
                        "phases": [p["phase"] for p in d.get("phases", [])]})
    return out


def phase(rubric: dict, name: str) -> dict | None:
    for p in rubric.get("phases", []):
        if p.get("phase") == name:
            return p
    return None


def first_phase(rubric: dict) -> str | None:
    ph = rubric.get("phases") or []
    return ph[0]["phase"] if ph else None


def next_phase(rubric: dict, current: str) -> str | None:
    names = [p["phase"] for p in rubric.get("phases", [])]
    if current in names:
        i = names.index(current)
        if i + 1 < len(names):
            return names[i + 1]
    return None


def all_points(rubric: dict) -> dict[str, dict]:
    """point_id -> {point, weight, phase, evidence_hint}. Used to score and to label evidence."""
    out = {}
    for p in rubric.get("phases", []):
        for m in p.get("must_hit", []):
            out[m["id"]] = dict(m, phase=p["phase"])
    return out
