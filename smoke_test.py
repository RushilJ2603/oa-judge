#!/usr/bin/env python3
"""End-to-end smoke test through the real judge path (no server needed).

For every runnable problem:
  - submit the REFERENCE as a user solution -> must AC every sample+hidden test.
  - submit the STUB -> must NOT AC (proves the test set actually discriminates).
Exits non-zero on any surprise.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))
from runner import execute, problems  # noqa: E402


def judge_all(pid, lang, source):
    p = problems.load(pid)
    compiled = execute.compile_for(lang, source)
    if not compiled.ok:
        execute.cleanup(compiled)
        return "CE", 0, 0
    limits, compare = p["meta"]["limits"], p["meta"]["compare"]
    cases = p["samples"] + p["hidden"]
    passed, overall = 0, "AC"
    for t in cases:
        v, _got, _err, _ms = execute.judge_case(
            lang, compiled, t["input"], t["output"],
            time_ms=limits["time_ms"], memory_mb=limits["memory_mb"], compare=compare)
        if v == "AC":
            passed += 1
        elif overall == "AC":
            overall = v
    execute.cleanup(compiled)
    return overall, passed, len(cases)


def main():
    ids = [d for d in sorted(os.listdir(os.path.join(os.path.dirname(__file__), "problems")))
           if os.path.exists(os.path.join(os.path.dirname(__file__), "problems", d, "problem.json"))]
    if len(sys.argv) > 1:
        ids = [i for i in ids if i in sys.argv[1:]]
    bad = 0
    print(f"{'PROBLEM':<34} {'REF':<22} {'STUB'}")
    print("-" * 74)
    for pid in ids:
        p = problems.load(pid)
        if not p["meta"]["runnable"]:
            print(f"{pid:<34} (statement-only)")
            continue
        lang = p["meta"]["languages"][0]
        ref = p["references"].get(lang)
        stub = p["stubs"].get(lang, "")
        rv, rp, rt = judge_all(pid, lang, ref) if ref else ("NO-REF", 0, 0)
        sv, sp, st = judge_all(pid, lang, stub)
        ref_ok = (rv == "AC" and rp == rt and rt > 0)
        stub_ok = (sv != "AC")               # stub must fail at least one test
        flag = "" if (ref_ok and stub_ok) else "   <<< PROBLEM"
        if not (ref_ok and stub_ok):
            bad += 1
        print(f"{pid:<34} {rv} {rp}/{rt}{'  OK' if ref_ok else ' !!':<6}   "
              f"{sv} {sp}/{st}{flag}")
    print("-" * 74)
    print("ALL GOOD" if bad == 0 else f"{bad} PROBLEM(S) NEED ATTENTION")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
