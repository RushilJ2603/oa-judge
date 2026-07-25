#!/usr/bin/env python3
"""One-command quality gate for a SINGLE candidate problem package (e.g. a Grok-authored one).

Nothing merges into the bank unless this prints GATE: PASS. It composes every existing check so the
guarantee is enforced by tooling, not by trusting whoever (or whatever) authored the package:

  1. structure     - audit.py rules: separate solution fn, required metadata, reference present,
                     >=5 edge tests incl. a max-scale one
  2. compile        - reference, stub, and brute all build
  3. anchor         - reference reproduces EVERY provided_test scraped from the source (ground truth
                     independent of the author). No provided tests -> must pass --allow-no-anchor
  4. samples        - reference reproduces every tests/sample/*.out
  5. brute          - an INDEPENDENT slow solution agrees with the reference on all provided tests
                     + many random generator inputs (catches a wrong reference)
  6. strength       - make_hidden + mutation_test: 100% mutation score, all planted wrongs killed
                     (catches a weak test suite)

Usage:
  python3 gate_candidate.py <candidate_dir> [--scraped path/to/slug.json] [--random N]
                            [--allow-no-anchor]
Exit 0 = PASS, non-zero = FAIL.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def gpp(src, out):
    return sh(["g++", "-std=c++17", "-O2", "-w", "-o", out, src])


def norm_tokens(s):
    return s.split()


def load_provided(scraped):
    if not scraped or not os.path.exists(scraped):
        return []
    d = json.load(open(scraped))
    out = []
    for t in (d.get("provided_tests") or []):
        i = str(t.get("input", ""))
        o = str(t.get("output", ""))
        if not i.endswith("\n"):
            i += "\n"
        out.append((i, o))
    return out


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cand = os.path.abspath(args[0])
    scraped = None
    random_n = 400
    allow_no_anchor = "--allow-no-anchor" in args
    for i, a in enumerate(args):
        if a == "--scraped":
            scraped = os.path.abspath(args[i + 1])
        if a == "--random":
            random_n = int(args[i + 1])

    pid = os.path.basename(cand.rstrip("/"))
    problem_json = os.path.join(cand, "problem.json")
    if not os.path.exists(problem_json):
        sys.exit(f"FAIL: no problem.json in {cand}")
    meta = json.load(open(problem_json))
    compare = meta.get("compare", "tokens")

    fails, warns = [], []

    def same(a, b):
        return norm_tokens(a) == norm_tokens(b) if compare == "tokens" else a.strip() == b.strip()

    # --- Stage the candidate into an isolated single-problem PROBLEMS dir so the existing whole-bank
    #     tools (verify_all / audit / make_hidden / mutation_test) run scoped to just this package. ---
    stage = tempfile.mkdtemp(prefix="gate_")
    pdir = os.path.join(stage, pid)
    shutil.copytree(cand, pdir)
    env = dict(os.environ, OAJ_PROBLEMS_DIR=stage)

    # 2. compile reference / stub / brute
    ref_cpp = os.path.join(pdir, "reference.cpp")
    ref_py = os.path.join(pdir, "reference.py")
    if os.path.exists(ref_cpp):
        r = gpp(ref_cpp, os.path.join(stage, "ref"))
        refcmd = [os.path.join(stage, "ref")]
        if r.returncode:
            fails.append("reference.cpp did not compile:\n" + r.stderr[:500])
    elif os.path.exists(ref_py):
        refcmd = [PY, ref_py]
    else:
        fails.append("no reference.cpp or reference.py")
        refcmd = None

    brute_cpp = os.path.join(pdir, "brute.cpp")
    brute_py = os.path.join(pdir, "brute.py")
    brutecmd = None
    if os.path.exists(brute_cpp):
        r = gpp(brute_cpp, os.path.join(stage, "brute"))
        brutecmd = [os.path.join(stage, "brute")]
        if r.returncode:
            fails.append("brute.cpp did not compile:\n" + r.stderr[:500])
            brutecmd = None
    elif os.path.exists(brute_py):
        brutecmd = [PY, brute_py]
    else:
        warns.append("no brute.* present (independent-solution cross-check skipped)")

    def run_in(cmd, data, to=30):
        try:
            return sh(cmd, input=data, timeout=to).stdout
        except subprocess.TimeoutExpired:
            return "<TIMEOUT>"

    # 3. anchor: reference must reproduce every provided_test from the source
    provided = load_provided(scraped)
    if refcmd and provided:
        bad = 0
        for inp, exp in provided:
            got = run_in(refcmd, inp)
            if not same(got, exp):
                bad += 1
        if bad:
            fails.append(f"anchor: reference fails {bad}/{len(provided)} scraped provided_tests")
    elif not provided and not allow_no_anchor:
        fails.append("anchor: no provided_tests found (pass --allow-no-anchor only if truly original)")

    # 4b. GENERATOR QUALITY (precondition for trusting the mutation gate). The mutation gate decides
    #     "equivalent vs real gap" by firing generator inputs at a survivor; a degenerate generator
    #     (no variety / ignores size) makes every real gap look equivalent and a weak suite passes.
    #     So a generator that doesn't vary its output or respond to the size arg is itself a failure.
    gen = os.path.join(pdir, "generator.py")
    if os.path.exists(gen):
        outs = []
        for seed, size in [(1, 3), (2, 3), (3, 10), (4, 10), (5, 40), (6, 40), (7, 150), (8, 150),
                           (9, 400), (10, 400)]:
            o = run_in([PY, gen, str(seed), str(size)], "", to=10)
            if o.strip():
                outs.append(o)
        distinct = len(set(outs))
        # Determinism: same (seed,size) MUST give the same input twice. A generator that reseeds from
        # the clock makes make_hidden draw different tests each run, so the mutation score flaps and
        # 100% can't be certified. This is the single most important generator property.
        d1 = run_in([PY, gen, "424242", "50"], "", to=10)
        d2 = run_in([PY, gen, "424242", "50"], "", to=10)
        if d1 != d2:
            fails.append("generator.py is NON-DETERMINISTIC: same seed gave different output. It must "
                         "`random.seed(int(sys.argv[1]))` so tests are reproducible and the score stable.")
        if len(outs) < 5:
            fails.append("generator.py produced too few valid inputs (needs `<seed> <size>` CLI)")
        elif distinct < max(5, int(0.6 * len(outs))):
            fails.append(f"generator.py is degenerate: only {distinct}/{len(outs)} distinct outputs "
                         f"— it must vary with seed. Test coverage from it cannot be trusted.")
        elif outs and max(len(o) for o in outs) <= min(len(o) for o in outs):
            fails.append("generator.py ignores the size arg (no max-scale input) — needed for TLE/"
                         "overflow coverage.")
    else:
        fails.append("no generator.py — required for random coverage + mutation-gate triage")
    if refcmd and brutecmd:
        bad = 0
        for inp, _ in provided:
            if not same(run_in(refcmd, inp), run_in(brutecmd, inp)):
                bad += 1
        if os.path.exists(gen):
            sizes = [3, 6, 12, 25, 60, 120]
            for k in range(random_n):
                inp = run_in([PY, gen, str(1000 + k), str(sizes[k % len(sizes)])], "", to=10)
                if not inp.strip():
                    continue
                if not same(run_in(refcmd, inp), run_in(brutecmd, inp)):
                    bad += 1
                    if bad <= 3:
                        fails.append(f"brute!=reference on generated input:\n{inp[:200]}")
                    break
        else:
            warns.append("no generator.py (random brute cross-check limited to provided tests)")
        if bad and not any("brute!=reference" in f for f in fails):
            fails.append(f"brute disagrees with reference on {bad} provided test(s)")
        # independence heuristic: brute source should differ substantially from reference source
        try:
            rs = open(ref_cpp if os.path.exists(ref_cpp) else ref_py).read()
            bs = open(brute_cpp if os.path.exists(brute_cpp) else brute_py).read()
            if rs.strip() == bs.strip():
                fails.append("brute is byte-identical to reference (not independent)")
        except Exception:
            pass

    # 1/4/6: reuse the whole-bank tools, scoped
    def stage_tool(name, extra=()):
        return sh([PY, os.path.join(ROOT, name), *extra], env=env)

    a = sh([PY, os.path.join(ROOT, "audit.py")], env=env)
    if a.returncode != 0:
        fails.append("audit.py hard-fail:\n" + (a.stdout + a.stderr)[-800:])

    mk = stage_tool("make_hidden.py", (pid, "14"))
    if mk.returncode != 0:
        fails.append("make_hidden.py failed:\n" + (mk.stdout + mk.stderr)[-500:])

    v = stage_tool("verify_all.py")
    if v.returncode != 0:
        fails.append("verify_all.py failed:\n" + (v.stdout + v.stderr)[-800:])

    mut = sh([PY, os.path.join(ROOT, "mutation_test.py"), pid], env=env)
    if mut.returncode != 0:
        fails.append("mutation_test weak suite:\n" + mut.stdout[-1200:])

    # report
    print("=" * 70)
    print(f"GATE for {pid}   (difficulty={meta.get('difficulty')}, source={meta.get('source')})")
    for w in warns:
        print("  WARN:", w)
    if fails:
        print("GATE: FAIL")
        for f in fails:
            print("  ✗", f)
        shutil.rmtree(stage, ignore_errors=True)
        sys.exit(1)
    print("GATE: PASS  (anchor + brute + structure + samples + 100% mutation)")
    shutil.rmtree(stage, ignore_errors=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
