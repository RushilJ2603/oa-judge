#!/usr/bin/env python3
"""Scaffold a new problem package.

    python3 add_problem.py <id> --title "..." [--company X] [--difficulty Easy|Medium|Hard]
                           [--lang cpp,py] [--runnable]

Creates problems/<id>/ with a problem.json, a placeholder statement.md, stub(s), and an empty
generator.py + tests/ dirs. You then fill statement.md + stub + generator, drop in a verified
reference.<lang>, and run:  python3 make_hidden.py <id>   then   python3 verify_all.py <id>
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

STUB_CPP = """#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    // Read input per the statement.
    // WRITE YOUR CODE HERE

    return 0;
}
"""

STUB_PY = """import sys
data = sys.stdin.read().split()

# WRITE YOUR CODE HERE
"""

GENERATOR = '''#!/usr/bin/env python3
"""Random input generator. argv[1]=seed, argv[2]=size hint. Prints ONE valid input instance."""
import random
import sys

seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
size = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rng = random.Random(seed)

# TODO: emit one valid input satisfying the constraints; keep small for `size` small.
n = rng.randint(1, max(1, size))
print(n)
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--title", required=True)
    ap.add_argument("--company", default="")
    ap.add_argument("--difficulty", default="Medium", choices=["Easy", "Medium", "Hard"])
    ap.add_argument("--lang", default="cpp", help="comma list of cpp,py")
    ap.add_argument("--tags", default="")
    ap.add_argument("--time-ms", type=int, default=2000)
    ap.add_argument("--memory-mb", type=int, default=256)
    ap.add_argument("--runnable", action="store_true", default=True)
    ap.add_argument("--statement-only", dest="runnable", action="store_false")
    args = ap.parse_args()

    langs = [x.strip() for x in args.lang.split(",") if x.strip()]
    pdir = os.path.join(ROOT, "problems", args.id)
    if os.path.exists(pdir):
        raise SystemExit(f"already exists: {pdir}")
    os.makedirs(os.path.join(pdir, "tests", "sample"))
    os.makedirs(os.path.join(pdir, "tests", "edge"))       # curated LC/OA-grade edge-case inputs
    os.makedirs(os.path.join(pdir, "tests", "hidden"))

    meta = {
        "id": args.id, "title": args.title, "company": args.company,
        "difficulty": args.difficulty,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "languages": langs if args.runnable else [],
        "runnable": args.runnable, "io_mode": "stdin_stdout", "compare": "tokens",
        "limits": {"time_ms": args.time_ms, "memory_mb": args.memory_mb},
        "origin": "", "links": [],
    }
    with open(os.path.join(pdir, "problem.json"), "w") as f:
        json.dump(meta, f, indent=2)
    with open(os.path.join(pdir, "statement.md"), "w") as f:
        f.write(f"# {args.title}\n\n_TODO: statement._\n\n## Input\n\n## Output\n\n"
                "## Constraints\n\n## Example\n\nInput:\n```\n```\nOutput:\n```\n```\n")
    if args.runnable:
        if "cpp" in langs:
            open(os.path.join(pdir, "stub.cpp"), "w").write(STUB_CPP)
        if "py" in langs:
            open(os.path.join(pdir, "stub.py"), "w").write(STUB_PY)
        open(os.path.join(pdir, "generator.py"), "w").write(GENERATOR)

    print(f"scaffolded {pdir}")
    print("next: fill statement.md, stub, generator.py; add a verified reference.<lang>;")
    print(f"      then  python3 make_hidden.py {args.id}  &&  python3 verify_all.py {args.id}")


if __name__ == "__main__":
    main()
