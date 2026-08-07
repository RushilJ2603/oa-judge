#!/usr/bin/env python3
"""Build a problem's hidden test set from its VERIFIED reference.

Hidden tests = two layers, both with outputs computed by running the reference (never hand-written):

  1. CURATED edge cases — hand-written input files in problems/<id>/tests/edge/*.in .
     This is where LC/OA-grade coverage lives: min/max bounds, empty/degenerate cases,
     all-same / all-distinct, sorted & reverse, overflow triggers, and the specific adversarial
     inputs that break common wrong solutions. These are durable; regenerating never deletes them.

  2. RANDOM cases — from problems/<id>/tests/generator.py across a spread of sizes, including the
     maximum size (for TLE discrimination).

Both are written into tests/hidden/ (curated as e##, random as r##). The reference is trusted
(each was brute-force verified), so its output IS the expected answer.

Usage:  python3 make_hidden.py <problem-id> [random_count] [--sizes s1,s2,...] [--seed-base N]
"""
import gzip
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def _write_gz(path_no_gz, text):
    """Write text to path_no_gz + '.gz'. Hidden tests are stored gzipped (~5-8x smaller) so the bank
    scales to 1000s of problems on the free 3GB volume. mtime=0 keeps the bytes deterministic so
    regenerating identical tests produces no git churn."""
    data = text.encode("utf-8")
    with open(path_no_gz + ".gz", "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(data)


def _read_plain_or_gz(path_no_gz):
    """Read a test file, transparently falling back to its gzipped sibling.
    Mirrors app/runner/problems.py::_read so tooling sees exactly what the judge sees."""
    if os.path.exists(path_no_gz):
        with open(path_no_gz, encoding="utf-8") as f:
            return f.read()
    gz = path_no_gz + ".gz"
    if os.path.exists(gz):
        with gzip.open(gz, "rt", encoding="utf-8") as f:
            return f.read()
    return None

# Honour OAJ_PROBLEMS_DIR so a candidate can be materialised in an isolated staging dir (this is how
# gate_candidate.py builds hidden tests for a not-yet-merged package without touching the live bank).
PROBLEMS = os.path.abspath(os.environ.get("OAJ_PROBLEMS_DIR") or os.path.join(ROOT, "problems"))
PY = sys.executable or "python3"


def compile_reference(pdir):
    if os.path.exists(os.path.join(pdir, "reference.cpp")):
        binp = os.path.join(pdir, ".ref_bin")
        r = subprocess.run(["g++", "-std=c++17", "-O2", "-w", "-o", binp,
                            os.path.join(pdir, "reference.cpp")], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"reference.cpp failed to compile:\n{r.stderr}")
        return [binp]
    if os.path.exists(os.path.join(pdir, "reference.py")):
        return [PY, os.path.join(pdir, "reference.py")]
    sys.exit("no reference.cpp or reference.py found")


def solve(refcmd, inp, timeout=30):
    rp = subprocess.run(refcmd, input=inp, capture_output=True, text=True, timeout=timeout)
    return rp.returncode, rp.stdout, rp.stderr


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pid = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else 12
    sizes = [5, 10, 25, 60, 120, 300, 800, 2000]
    seed_base = 1000
    for a in sys.argv:
        if a.startswith("--sizes="):
            sizes = [int(x) for x in a.split("=", 1)[1].split(",")]
        if a.startswith("--seed-base="):
            seed_base = int(a.split("=", 1)[1])

    pdir = os.path.join(PROBLEMS, pid)
    hidden = os.path.join(pdir, "tests", "hidden")
    edge = os.path.join(pdir, "tests", "edge")
    os.makedirs(hidden, exist_ok=True)
    for f in os.listdir(hidden):                       # clear generated hidden (edge/ is preserved)
        os.remove(os.path.join(hidden, f))

    refcmd = compile_reference(pdir)

    # --- layer 1: curated edge cases (durable inputs, reference-computed outputs) ---
    n_edge = 0
    if os.path.isdir(edge):
        # Curated edge inputs may be stored gzipped (.in.gz) — large ones are compressed to keep the
        # bank hostable. Iterate LOGICAL stems so both spellings are found: silently skipping a
        # gzipped edge here would weaken every hidden suite built from it, with no visible error.
        stems = sorted({f[:-6] if f.endswith(".in.gz") else f[:-3]
                        for f in os.listdir(edge) if f.endswith((".in", ".in.gz"))})
        for fn in (s + ".in" for s in stems):
            inp = _read_plain_or_gz(os.path.join(edge, fn))
            if inp is None:
                print(f"  EDGE unreadable (no .in or .in.gz): {fn}")
                continue
            rc, out, err = solve(refcmd, inp)
            if rc != 0:
                print(f"  EDGE reference FAILED on {fn}: rc={rc} {err.strip()[:120]}")
                continue
            n_edge += 1
            _write_gz(os.path.join(hidden, f"e{n_edge:02d}.in"), inp)
            _write_gz(os.path.join(hidden, f"e{n_edge:02d}.out"), out)

    # --- layer 2: random cases across sizes (incl. the max) ---
    gen = os.path.join(pdir, "generator.py")
    n_rand = 0
    if os.path.exists(gen):
        for k in range(count):
            size = sizes[k % len(sizes)]
            seed = seed_base + k
            gp = subprocess.run([PY, gen, str(seed), str(size)],
                                capture_output=True, text=True, timeout=20)
            if gp.returncode != 0 or not gp.stdout.strip():
                print(f"  generator failed (seed={seed}, size={size}): {gp.stderr.strip()[:100]}")
                continue
            rc, out, err = solve(refcmd, gp.stdout)
            if rc != 0:
                print(f"  reference failed on seed={seed}: rc={rc} {err.strip()[:100]}")
                continue
            n_rand += 1
            _write_gz(os.path.join(hidden, f"r{n_rand:02d}.in"), gp.stdout)
            _write_gz(os.path.join(hidden, f"r{n_rand:02d}.out"), out)

    b = os.path.join(pdir, ".ref_bin")
    if os.path.exists(b):
        os.remove(b)
    print(f"{pid}: {n_edge} curated edge + {n_rand} random = {n_edge + n_rand} hidden tests")


if __name__ == "__main__":
    main()
