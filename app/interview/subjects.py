"""Subject taxonomy and interview-importance weights for the rubric corpus.

Two jobs:

1. **Give every rubric a real subject.** The corpus ids carry a source prefix (os_, dbms_, cpp_,
   c_, py_, dsa_) but those prefixes lie in one place: the aptitude/quant material lives under the
   DSA notes tree, so `dsa_s02_percentages` is not DSA at all. A flat "CS Fundamentals" list of 200+
   entries mixing OS, C++ and percentage arithmetic is unusable, so subject is resolved here rather
   than trusted from the id.

2. **Weight topics by how much interviews actually care.** Deadlocks, indexing and pointers come up
   constantly; build systems and further-reading sections almost never. Weight drives ordering in
   the catalog and selection in mixed rounds, so practice time lands where it pays.

Weights are 1-5 (5 = asked in almost every loop). They are deliberately coarse — the point is to
separate "always asked" from "nice to know", not to pretend at precision.
"""
import re

# ---------------------------------------------------------------- subjects
SUBJECTS = {
    "os":       {"label": "Operating Systems",   "order": 1},
    "dbms":     {"label": "DBMS & SQL",          "order": 2},
    "cpp":      {"label": "C++ & OOP",           "order": 3},
    "c":        {"label": "C Programming",       "order": 4},
    "py":       {"label": "Python",              "order": 5},
    "dsa":      {"label": "Data Structures & Algorithms", "order": 6},
    "aptitude": {"label": "Aptitude & Quant",    "order": 7},
    # non-FUND types keep their own buckets
    "cp":       {"label": "Competitive Programming", "order": 8},
    "hld":      {"label": "System Design (HLD)", "order": 9},
    "lld":      {"label": "Low-Level Design",    "order": 10},
    "sdfound":  {"label": "System Design Foundations", "order": 11},
}

# The DSA notes tree holds BOTH real data-structures material and the aptitude/quant set, and the
# section numbers interleave them (dsa_s26 is "Advanced String Algorithms" *and* "Mental Math").
# So the id number decides nothing — classification is by title, which is clean and distinct.
_APTITUDE_WORDS = (
    "percentage", "profit", "loss", "discount", "ratio", "proportion", "average", "mixture",
    "alligation", "permutation", "combination", "probability", "mensuration", "geometry",
    "clock", "calendar", "aptitude", "mental math", "number system", "divisibility",
    "simple interest", "compound interest", "progression", "series", "puzzle", "seating",
    "arrangement", "cube", "dice", "critical reasoning", "truth-teller", "non-verbal",
    "data interpretation", "data sufficiency", "ranking", "expected value", "fair game",
    "time & work", "time and work", "speed", "distance", "algebra", "equations",
)
# Wins over the aptitude list when both match — these are unambiguously DSA even if a word like
# "series" or "arrangement" appears in the title.
_DSA_WORDS = (
    "array", "string algorithm", "linked list", "stack", "queue", "tree", "bst", "graph",
    "dynamic programming", "trie", "range quer", "sort", "search", "hash", "heap", "greedy",
    "backtrack", "recursion", "complexity", "c++ essentials", "toolbox", "sliding window",
    "two pointer", "prefix sum", "bit manipulation", "segment tree", "fenwick", "union-find",
    "disjoint set", "shortest path", "traversal",
)


def subject_of(rubric: dict) -> str:
    t = rubric.get("type", "")
    if t == "HLD":
        return "hld"
    if t == "LLD":
        return "lld"
    if t == "CONCEPT":
        return "sdfound"
    if t == "CP":
        return "cp"
    rid = rubric.get("id", "")
    if rid.startswith("dsa_"):
        title = (rubric.get("title", "") or "").lower()
        if any(w in title for w in _DSA_WORDS):
            return "dsa"                                   # DSA wins ties
        if any(w in title for w in _APTITUDE_WORDS):
            return "aptitude"
        return "dsa"
    for pre in ("dbms", "cpp", "os", "py", "c"):
        if rid.startswith(pre + "_"):
            return pre
    return "dsa"


def subject_label(key: str) -> str:
    return SUBJECTS.get(key, {}).get("label", key)


# ---------------------------------------------------------------- importance
# Topics that carry an interview loop. Matched against the title, lowercased.
_HIGH = (
    "deadlock", "process", "thread", "scheduling", "synchron", "virtual memory", "paging",
    "memory management", "file system", "concurrency", "mutex", "semaphore",
    "index", "normal", "transaction", "acid", "join", "query", "sql", "isolation", "lock",
    "pointer", "memory", "reference", "polymorph", "inherit", "virtual", "template",
    "stl", "smart pointer", "raii", "const", "constructor", "destructor", "move",
    "hash", "tree", "graph", "sort", "search", "dynamic programming", "recursion",
    "linked list", "stack", "queue", "heap", "array", "string", "greedy", "binary search",
    "complexity", "big-o", "move semantic", "rvalue", "lambda", "exception", "operator overload",
)
# Careful with substrings here: a bare "reference" also matches "Rvalue References" and "Passing by
# Reference", which are core C++ interview topics — it demoted them to 1 until this was caught.
# Every entry must be a phrase that cannot appear inside a genuinely important title.
_LOW = (
    "further reading", "open question", "orientation", "appendix", "glossary",
    "resources", "history", "toolchain", "installation", "setup", "front matter",
    "preprocessor", "comment style", "formatting", "further study", "what next",
)


def weight_of(rubric: dict) -> int:
    """1-5. Blends topic keywords with the rubric's own relevance line and depth."""
    title = (rubric.get("title", "") or "").lower()
    rel = (rubric.get("relevance", "") or "").lower()
    if any(w in title for w in _LOW):
        return 1
    w = 3
    if any(k in title for k in _HIGH):
        w += 1
    # The generated relevance line usually opens with a High/Medium/Low judgement.
    if rel.startswith("high") or "very common" in rel or "almost every" in rel:
        w += 1
    elif rel.startswith("low") or "rarely" in rel or "niche" in rel:
        w -= 1
    if rubric.get("difficulty") == "senior":
        w -= 1                       # deep specialisations are asked less often than core topics
    return max(1, min(5, w))


def enrich(meta: dict, rubric: dict) -> dict:
    """Attach subject + weight to a catalog entry."""
    key = subject_of(rubric)
    meta["subject"] = key
    meta["subject_label"] = subject_label(key)
    meta["subject_order"] = SUBJECTS.get(key, {}).get("order", 99)
    meta["weight"] = weight_of(rubric)
    return meta
