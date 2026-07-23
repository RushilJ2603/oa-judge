"""Stress testing: random inputs -> reference vs user, then shrink the first failure.

This is the app's answer to "I can't see the failing test". It needs:
  - generator.py in the problem (prints one random input; argv[1]=seed, argv[2]=size)
  - a verified reference solution in the problem
The user's code is compared to the reference on many random small inputs; the first disagreement is
minimised (by re-rolling smaller sizes that still fail) so the counterexample is human-readable.

Performance: the reference and the user program are each compiled EXACTLY ONCE and their binaries are
reused across every iteration and the shrink phase. (Recompiling per-iteration made a 300-iteration
run do ~1000 compilations — the original, unusable version.)
"""
import subprocess
import sys

from . import execute, judge

PYTHON = sys.executable or "python3"


def _gen(generator_path: str, seed: int, size: int) -> str | None:
    try:
        proc = subprocess.run([PYTHON, generator_path, str(seed), str(size)],
                              capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _compile_reference(problem):
    """Compile the reference once. Returns (lang, compiled) or (None, None)."""
    for lang in ("cpp", "py"):
        ref_src = problem["references"].get(lang)
        if ref_src is None:
            continue
        compiled = execute.compile_for(lang, ref_src)
        if compiled.ok:
            return lang, compiled
        execute.cleanup(compiled)
    return None, None


def _ref_output(ref_lang, ref_compiled, problem, inp: str):
    """Reference answer for one input, using the PRE-COMPILED reference. (ok, output)."""
    res = execute.run_once(ref_lang, ref_compiled, inp,
                           time_ms=problem["meta"]["limits"]["time_ms"],
                           memory_mb=problem["meta"]["limits"]["memory_mb"])
    if judge.verdict_for_run(res, memory_mb=problem["meta"]["limits"]["memory_mb"]) is None:
        return True, res.stdout
    return False, None


def run(problem, language: str, user_source: str, iterations: int = 300) -> dict:
    if problem["generator_path"] is None:
        return {"status": "no_generator", "checked": 0, "counterexample": None,
                "message": "This problem has no random generator, so stress testing is unavailable."}
    if not problem["references"]:
        return {"status": "no_generator", "checked": 0, "counterexample": None,
                "message": "No reference solution to check against."}

    user = execute.compile_for(language, user_source)
    if not user.ok:
        out = user.compile_output
        execute.cleanup(user)
        return {"status": "error", "checked": 0, "counterexample": None,
                "message": "Your code did not compile:\n" + out}

    ref_lang, ref = _compile_reference(problem)
    if ref is None:
        execute.cleanup(user)
        return {"status": "error", "checked": 0, "counterexample": None,
                "message": "The reference solution failed to compile (internal)."}

    limits = problem["meta"]["limits"]
    compare = problem["meta"]["compare"]
    gen = problem["generator_path"]

    try:
        first_fail = None
        checked = 0
        for i in range(iterations):
            inp = _gen(gen, seed=i + 1, size=8)
            if inp is None:
                continue
            checked += 1
            ok_ref, exp = _ref_output(ref_lang, ref, problem, inp)
            if not ok_ref:
                continue                     # reference itself failed on this input; skip
            v, got, _stderr, _t = execute.judge_case(
                language, user, inp, exp,
                time_ms=limits["time_ms"], memory_mb=limits["memory_mb"], compare=compare)
            if v != "AC":
                first_fail = (inp, exp, got if v == "WA" else v)
                break

        if first_fail is None:
            return {"status": "clean", "checked": checked, "counterexample": None,
                    "message": f"No counterexample in {checked} random cases. "
                               f"That is evidence, not proof — try more iterations or a larger size."}

        # If the first failure is already small enough to read, skip the (expensive) shrink phase.
        if len(first_fail[0]) <= 40:
            return {"status": "counterexample", "checked": checked,
                    "counterexample": {"input": first_fail[0], "expected": first_fail[1],
                                       "got": first_fail[2]}, "message": ""}

        # Shrink: re-roll smaller sizes; keep the smallest input (by length) that still fails.
        best = first_fail
        for size in (1, 2, 3, 4, 5, 6):
            for seed in range(1, 120):
                inp = _gen(gen, seed=seed, size=size)
                if inp is None:
                    continue
                ok_ref, exp = _ref_output(ref_lang, ref, problem, inp)
                if not ok_ref:
                    continue
                v, got, _stderr, _t = execute.judge_case(
                    language, user, inp, exp,
                    time_ms=limits["time_ms"], memory_mb=limits["memory_mb"], compare=compare)
                if v != "AC" and len(inp) < len(best[0]):
                    best = (inp, exp, got if v == "WA" else v)
            if len(best[0]) <= 40:               # small enough to read; stop early
                break

        return {
            "status": "counterexample", "checked": checked,
            "counterexample": {"input": best[0], "expected": best[1], "got": best[2]},
            "message": "",
        }
    finally:
        execute.cleanup(user)
        execute.cleanup(ref)
