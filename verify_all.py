#!/usr/bin/env python3
"""Integration gate: verify every problem package is internally consistent.

For each runnable problem:
  1. stub compiles (g++) / parses (py_compile)          -> solver won't hit a syntax error they didn't cause
  2. reference compiles/parses
  3. reference reproduces EVERY sample .out              -> catches agent sample-transcription errors + I/O drift
  4. generator (if present) emits inputs the reference consumes without error
Prints a per-problem PASS/FAIL table and exits non-zero if anything failed.

This does NOT trust anything an agent produced — it runs the code. Reference correctness itself was
established earlier by brute-force cross-checks; here we only confirm the *package* is wired right.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROBLEMS = os.path.join(ROOT, "problems")
PY = sys.executable or "python3"


def compile_cpp(path, out):
    r = subprocess.run(["g++", "-std=c++17", "-O2", "-w", "-o", out, path],
                       capture_output=True, text=True)
    return r.returncode == 0, r.stderr


def parse_py(path):
    r = subprocess.run([PY, "-m", "py_compile", path], capture_output=True, text=True)
    return r.returncode == 0, r.stderr


def run(cmd, stdin, timeout=30):
    try:
        r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"


def tokens(s):
    return s.split()


def check_problem(pid):
    pdir = os.path.join(PROBLEMS, pid)
    meta = json.load(open(os.path.join(pdir, "problem.json")))
    issues = []
    if not meta.get("runnable", True):
        return "SKIP", ["statement-only (runnable=false)"]

    langs = meta.get("languages", [])
    tmp = os.path.join(pdir, ".verify_tmp")
    os.makedirs(tmp, exist_ok=True)

    # --- stub compiles ---
    for lang in langs:
        stub = os.path.join(pdir, "stub." + ("cpp" if lang == "cpp" else "py"))
        if not os.path.exists(stub):
            issues.append(f"missing stub.{lang}")
            continue
        if lang == "cpp":
            ok, err = compile_cpp(stub, os.path.join(tmp, "stub_bin"))
        else:
            ok, err = parse_py(stub)
        if not ok:
            issues.append(f"stub.{lang} does not compile: {err.strip().splitlines()[0] if err.strip() else '?'}")

    # --- reference compiles + runs samples ---
    ref_cmd = None
    if os.path.exists(os.path.join(pdir, "reference.cpp")):
        ok, err = compile_cpp(os.path.join(pdir, "reference.cpp"), os.path.join(tmp, "ref_bin"))
        if ok:
            ref_cmd = [os.path.join(tmp, "ref_bin")]
        else:
            issues.append(f"reference.cpp compile FAIL: {err.strip().splitlines()[-1] if err.strip() else '?'}")
    elif os.path.exists(os.path.join(pdir, "reference.py")):
        ok, err = parse_py(os.path.join(pdir, "reference.py"))
        if ok:
            ref_cmd = [PY, os.path.join(pdir, "reference.py")]
        else:
            issues.append("reference.py parse FAIL")
    else:
        issues.append("no reference.* present")

    compare = meta.get("compare", "tokens")
    sample_dir = os.path.join(pdir, "tests", "sample")
    n_samples = 0
    if ref_cmd and os.path.isdir(sample_dir):
        for fn in sorted(os.listdir(sample_dir)):
            if not fn.endswith(".in"):
                continue
            n_samples += 1
            inp = open(os.path.join(sample_dir, fn)).read()
            exp = open(os.path.join(sample_dir, fn[:-3] + ".out")).read()
            rc, got, err = run(ref_cmd, inp)
            if rc != 0:
                issues.append(f"reference crashed on sample {fn} (rc={rc})")
            elif tokens(exp) != tokens(got):
                issues.append(f"SAMPLE MISMATCH {fn}: expected {tokens(exp)[:6]} got {tokens(got)[:6]}")
    if n_samples == 0:
        issues.append("no sample tests")

    # --- generator emits reference-consumable inputs ---
    gen = os.path.join(pdir, "generator.py")
    if os.path.exists(gen) and ref_cmd:
        gok = parse_py(gen)[0]
        if not gok:
            issues.append("generator.py does not parse")
        else:
            bad = 0
            for seed in range(1, 6):
                rc, out, err = run([PY, gen, str(seed), "6"], "", timeout=15)
                if rc != 0 or not out.strip():
                    bad += 1
                    continue
                rc2, _, _ = run(ref_cmd, out)
                if rc2 != 0:
                    bad += 1
            if bad:
                issues.append(f"generator produced {bad}/5 inputs the reference rejected")
    elif not os.path.exists(gen):
        issues.append("(no generator.py — stress disabled)")

    # cleanup
    for f in os.listdir(tmp):
        try:
            os.remove(os.path.join(tmp, f))
        except OSError:
            pass
    os.rmdir(tmp)

    hard = [i for i in issues if not i.startswith("(")]
    return ("PASS" if not hard else "FAIL"), issues


def main():
    ids = sorted(d for d in os.listdir(PROBLEMS)
                 if os.path.exists(os.path.join(PROBLEMS, d, "problem.json")))
    if len(sys.argv) > 1:
        ids = [i for i in ids if i in sys.argv[1:]]
    worst = 0
    print(f"{'PROBLEM':<34} {'STATUS'}")
    print("-" * 60)
    for pid in ids:
        status, issues = check_problem(pid)
        print(f"{pid:<34} {status}")
        for it in issues:
            print(f"    - {it}")
        if status == "FAIL":
            worst = 1
    print("-" * 60)
    print("OK" if worst == 0 else "FAILURES PRESENT")
    sys.exit(worst)


if __name__ == "__main__":
    main()
