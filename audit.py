#!/usr/bin/env python3
"""Structural authoring gate for the problem bank.

`verify_all.py` proves every reference is *correct* (ACs its own tests). This script proves every
package is *shaped right* — the checks a wrong output can't catch. It exists because a batch of
stubs once regressed to solving inside main() instead of exposing a separate solution function;
this gate makes that class of mistake fail loudly instead of shipping.

Run from the repo root:  python3 audit.py
Exit code 0 = no hard failures (warnings are allowed). Non-zero = a hard rule was broken.
"""
import json
import os
import re
import sys

BANK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "problems")

# A top-level C++ function definition: an identifier(...) at column 0, optionally opening a brace.
_FUNC = re.compile(r"^[A-Za-z_][\w:<>,&*\s]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{?\s*$", re.M)
REQUIRED_META = ("id", "title", "difficulty", "source")


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _strip_py_comments(src: str) -> str:
    return re.sub(r"#[^\n]*", "", src)


def _cpp_functions(src: str) -> list[str]:
    return _FUNC.findall(_strip_comments(src))


def audit() -> tuple[list[str], list[str]]:
    hard, warn = [], []
    for pid in sorted(os.listdir(BANK)):
        pdir = os.path.join(BANK, pid)
        pj = os.path.join(pdir, "problem.json")
        if not os.path.isfile(pj):
            continue
        try:
            meta = json.load(open(pj, encoding="utf-8"))
        except json.JSONDecodeError as e:
            hard.append(f"{pid}: problem.json is not valid JSON ({e})")
            continue

        for key in REQUIRED_META:
            if not meta.get(key):
                hard.append(f"{pid}: missing required metadata '{key}'")
        if meta.get("source") not in ("tuf", "oa-helper", "gyan"):
            warn.append(f"{pid}: source '{meta.get('source')}' is not one of tuf/oa-helper/gyan")

        runnable = meta.get("runnable", True)
        langs = meta.get("languages", [])

        if not runnable:
            # Statement-only. Direct-LeetCode wrappers MUST carry the link (that's the whole point of
            # not re-judging them). Non-judgeable ones (e.g. SQL with no LC twin) may omit it.
            if not meta.get("links"):
                warn.append(f"{pid}: statement-only with no links[] — fine only if it has no "
                            f"LeetCode equivalent; a direct-LC wrapper MUST link out")
            continue

        # Runnable: each declared language needs a stub, and the C++ stub must expose a named
        # solution function (the rule that regressed). main() should only do I/O.
        for lang, fname in (("cpp", "stub.cpp"), ("py", "stub.py")):
            if lang in langs and not os.path.isfile(os.path.join(pdir, fname)):
                hard.append(f"{pid}: languages lists '{lang}' but {fname} is missing")
        if "cpp" in langs and os.path.isfile(os.path.join(pdir, "stub.cpp")):
            names = _cpp_functions(open(os.path.join(pdir, "stub.cpp"), encoding="utf-8").read())
            if "main" not in names:
                hard.append(f"{pid}: stub.cpp has no main()")
            if not [n for n in names if n != "main"]:
                hard.append(f"{pid}: stub.cpp solves inside main() — needs a SEPARATE solution "
                            f"function with the // WRITE YOUR CODE HERE marker (the stub rule)")
        if "py" in langs and os.path.isfile(os.path.join(pdir, "stub.py")):
            defs = re.findall(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", _strip_py_comments(
                open(os.path.join(pdir, "stub.py"), encoding="utf-8").read()), re.M)
            if not [n for n in defs if n != "main"]:
                hard.append(f"{pid}: stub.py solves inline — needs a SEPARATE solution function "
                            f"(main() only reads stdin and prints) (the stub rule)")
        # A reference is required to judge a runnable problem.
        if not any(os.path.isfile(os.path.join(pdir, f"reference.{ext}")) for ext in ("cpp", "py")):
            hard.append(f"{pid}: runnable but has no reference.cpp/reference.py")

    return hard, warn


def main() -> int:
    hard, warn = audit()
    if warn:
        print("WARNINGS (allowed):")
        for w in warn:
            print("  ⚠ ", w)
        print()
    if hard:
        print("HARD FAILURES:")
        for h in hard:
            print("  ✗ ", h)
        print(f"\n{len(hard)} hard failure(s). Fix before publishing.")
        return 1
    print("Structural audit clean ✓  (no hard failures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
