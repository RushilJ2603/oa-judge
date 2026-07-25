#!/usr/bin/env python3
"""Test-strength gate: mutation testing for the problem bank.

`verify_all.py` proves the reference is correct. `audit.py` proves the package is shaped right.
Neither proves the *tests are strong enough to catch a wrong submission* — that is what let a bugged
Goldman "unstable-tasks" solution pass 17/18 cases. This gate measures that directly.

Method (standard mutation testing, à la PIT / mutmut / Stryker):
  1. Take the VERIFIED reference and apply one small, behaviour-changing edit at a time
     (flip a comparison, swap min/max, +/-, &&/||, off-by-one) -> a "mutant" = a plausible wrong
     solution.
  2. A mutant is KILLED if it disagrees with the reference on ANY input in the problem's full
     judged test set (sample + edge + hidden). It SURVIVES if every test produces identical output.
  3. A surviving mutant is a bug class the tests cannot see -> the suite is too weak. Add an edge
     case that distinguishes it, regenerate hidden, and it dies.

Mutation score = killed / (killed + survived). The bar for shipping is 100% (every non-equivalent
mutant killed); a genuinely equivalent mutant may be whitelisted in <problem>/.mutants_ok .

Planted wrongs (stronger, human-authored traps): any file under problems/<id>/wrong/*.{cpp,py} is a
known-wrong solution that MUST be killed by the suite. These lock in specific traps (e.g. the
sort-a-copy bug) so they can never regress.

Usage:
  python3 mutation_test.py <problem-id>     # one problem, verbose survivors
  python3 mutation_test.py --all            # whole bank, summary + non-zero exit on any survivor
  python3 mutation_test.py <id> --quick      # skip the largest (slowest) test inputs
"""
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
PROBLEMS = os.path.abspath(os.environ.get("OAJ_PROBLEMS_DIR") or os.path.join(ROOT, "problems"))
PY = sys.executable or "python3"

# --- C++ operator mutations. Multi-char ops are matched first so we never split "<=" into "<". ---
# Each entry: canonical token -> list of replacements that change behaviour.
CPP_OPS = [
    ("<=", ["<", ">", ">="]),
    (">=", [">", "<", "<="]),
    ("==", ["!="]),
    ("!=", ["=="]),
    ("&&", ["||"]),
    ("||", ["&&"]),
    ("<", ["<=", ">"]),
    (">", [">=", "<"]),
    ("+", ["-"]),
    ("-", ["+"]),
]
# Word-level swaps (identifier boundaries).
CPP_WORDS = [("min", "max"), ("max", "min")]

# Operators we must NOT confuse a single '<'/'>' with, or a '+'/'-' inside, while scanning.
_MULTI = ["<<=", ">>=", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||",
          "++", "--", "+=", "-=", "*=", "/=", "->", "::"]


def _strip_line_comments(src):
    # Keep length identical so offsets stay valid: blank out comment/string bodies.
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            while i < n and src[i] != '\n':
                out[i] = ' '; i += 1
        elif c == '/' and i + 1 < n and src[i + 1] == '*':
            out[i] = ' '; out[i + 1] = ' '; i += 2
            while i + 1 < n and not (src[i] == '*' and src[i + 1] == '/'):
                if src[i] != '\n':
                    out[i] = ' '
                i += 1
            if i + 1 < n:
                out[i] = ' '; out[i + 1] = ' '; i += 2
        elif c in '"\'':
            q = c; out[i] = ' '; i += 1
            while i < n and src[i] != q:
                if src[i] == '\\' and i + 1 < n:
                    out[i] = ' '; out[i + 1] = ' '; i += 2; continue
                out[i] = ' '; i += 1
            if i < n:
                out[i] = ' '; i += 1
        else:
            i += 1
    # Blank preprocessor lines entirely: the '<'/'>' in `#include <bits/stdc++.h>` are not operators.
    masked = "".join(out)
    lines, pos = [], 0
    for ln in masked.splitlines(keepends=True):
        lines.append(" " * len(ln) if ln.lstrip().startswith("#") else ln)
    return "".join(lines)


def cpp_mutants(src):
    """Yield (label, mutated_src). Offsets computed on a comment/string-masked copy so we never
    mutate inside a comment or literal, but splice into the ORIGINAL source."""
    mask = _strip_line_comments(src)
    seen = set()
    muts = []
    i, n = 0, len(mask)
    while i < n:
        # Skip over multi-char operators we don't mutate but must not mis-scan.
        skip = next((m for m in _MULTI if mask.startswith(m, i)), None)
        # Try to match a mutable operator (longest first via CPP_OPS ordering with multis handled).
        matched = None
        for tok, reps in CPP_OPS:
            if mask.startswith(tok, i):
                # Ensure we're not inside a longer multi op (e.g. '<' inside '<<').
                longer = next((m for m in _MULTI if mask.startswith(m, i) and len(m) > len(tok)), None)
                if longer:
                    break
                matched = (tok, reps)
                break
        if matched:
            tok, reps = matched
            for r in reps:
                mutated = src[:i] + r + src[i + len(tok):]
                key = (i, tok, r)
                if key not in seen:
                    seen.add(key)
                    muts.append((f"@{i} '{tok}'->'{r}'", mutated))
            i += len(tok)
            continue
        if skip:
            i += len(skip); continue
        i += 1
    # word swaps
    for w, r in CPP_WORDS:
        for m in re.finditer(r"\b" + re.escape(w) + r"\b", mask):
            j = m.start()
            mutated = src[:j] + r + src[j + len(w):]
            muts.append((f"@{j} '{w}'->'{r}'", mutated))
    return muts


_IO_SKIP = ("cin", "cout", "printf", "scanf", "ios::sync", ".tie", "return", "getline")


def cpp_deletion_mutants(src):
    """Blank one whole statement at a time (a real bug class: a missing/ineffective update, e.g. the
    unstable-tasks 'sort a copy' bug behaves like the sort statement being deleted). Statements are
    split at ';' occurring at paren-depth 0 inside a function body; declaration/I-O statements are
    skipped (deleting a declaration just fails to compile, which is noise)."""
    mask = _strip_line_comments(src)
    muts = []
    bdepth = pdepth = 0
    start = 0  # start offset of the current statement
    for i, c in enumerate(mask):
        if c == '{':
            bdepth += 1; start = i + 1
        elif c == '}':
            bdepth = max(0, bdepth - 1); start = i + 1
        elif c == '(':
            pdepth += 1
        elif c == ')':
            pdepth = max(0, pdepth - 1)
        elif c == ';' and pdepth == 0 and bdepth >= 1:
            stmt = mask[start:i]
            body = stmt.strip()
            if body and not any(tok in stmt for tok in _IO_SKIP) and re.search(
                    r"[^=<>!+\-*/]=[^=]|\+\+|--|\+=|-=|\bsort\b|\bswap\b|"
                    r"push_back|emplace|insert|erase|\bpop\b|reverse|accumulate", stmt):
                mutated = src[:start] + (" " * (i - start)) + src[i + 1:]
                muts.append((f"del@{start} '{body[:40]}'", mutated))
            start = i + 1
    return muts


def collect_inputs(pdir, quick=False):
    """All judged inputs, smallest-first so a wrong mutant dies on a cheap case before the big ones."""
    files = []
    for sub in ("sample", "edge", "hidden"):
        d = os.path.join(pdir, "tests", sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".in"):
                p = os.path.join(d, f)
                files.append((os.path.getsize(p), p))
    files.sort()
    if quick and len(files) > 4:
        files = files[: max(4, len(files) // 2)]
    return [p for _, p in files]


_PCHDIR = os.path.join("/tmp", "oaj_mut_pch")


def build_pch():
    """Precompile <bits/stdc++.h> once; mutants route their include through it (~4x faster compile)."""
    os.makedirs(_PCHDIR, exist_ok=True)
    open(os.path.join(_PCHDIR, "all.h"), "w").write("#include <bits/stdc++.h>\n")
    subprocess.run(["g++", "-std=c++17", "-O0", "-w", "-x", "c++-header",
                    os.path.join(_PCHDIR, "all.h"), "-o", os.path.join(_PCHDIR, "all.h.gch")],
                   capture_output=True, text=True)


def compile_cpp(src_path, out_path, pch=False):
    if pch:
        args = ["g++", "-std=c++17", "-O0", "-w", "-I", _PCHDIR, "-o", out_path, src_path]
    else:
        args = ["g++", "-std=c++17", "-O2", "-w", "-o", out_path, src_path]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode == 0, r.stderr


def compile_src(src, out_path, idx, pch=True):
    """Compile a mutant source STRING (routing the heavy include through the PCH)."""
    src = src.replace("#include <bits/stdc++.h>", '#include "all.h"', 1)
    tmp = out_path + f".{idx}.cpp"
    open(tmp, "w").write(src)
    ok, err = compile_cpp(tmp, out_path + f".{idx}", pch=pch)
    return (ok, out_path + f".{idx}")


# A run is "unreliable" if it timed out or errored. Under CPU load (many mutants compiling/running in
# parallel) a perfectly correct program can transiently exceed the wall-clock limit; if we treated
# that sentinel as a real output value, a mutant's verdict would flip between runs and the score would
# flap (observed 100%->96.8%). So a timeout is NEVER a data point — it is a skipped observation.
TIMEOUT_SENTINEL = "<TIMEOUT>"
BASE_TIMEOUT = 25  # generous: the reference is O(optimal); only contention makes it slow


def _unreliable(x):
    return x == TIMEOUT_SENTINEL or x.startswith("<ERR")


def run(cmd, stdin, timeout=BASE_TIMEOUT):
    try:
        r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
        # A NON-ZERO exit (segfault / abort / uncaught throw) is unreliable, NOT an output value of "".
        # This matters for triage: the fuzzer can nudge a value out of its stated range (r>M, l=0),
        # crashing an otherwise-correct reference. If we read the crash as empty stdout, any mutant
        # that DOESN'T crash "differs" from it and we persist the crash input as a bogus edge test.
        # Flagging it unreliable makes the oracle DROP such inputs and triage SKIP them instead.
        if r.returncode != 0:
            return f"<ERR rc={r.returncode}>"
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return TIMEOUT_SENTINEL
    except Exception as e:
        return f"<ERR {e}>"


def norm(s):
    return "\n".join(" ".join(line.split()) for line in s.strip().splitlines())


def make_same(compare):
    """Compare two program outputs *exactly the way the judge does*, so a mutant that only differs
    in whitespace under `compare: tokens` is correctly treated as equivalent (not a weak suite)."""
    if compare == "tokens":
        return lambda a, b: a.split() == b.split()
    return lambda a, b: norm(a) == norm(b)  # 'exact' / line-structured


def oracle_outputs(refcmd, inputs):
    """Reference output for every input, computed RELIABLY, plus the reference's own worst-case
    runtime. If the reference times out on an input under load, retry once with a generous timeout;
    if it still times out, that input is dropped (returned separately) so it can never poison a
    mutant comparison with a phantom `<TIMEOUT>` value. Because every kept input is proven
    reference-tractable, a MUTANT that later times out on one is a genuine divergence, not noise.
    Returns (oracle, kept_inputs, dropped_inputs, max_ref_seconds)."""
    import time
    out, kept, dropped, max_t = {}, [], [], 0.0
    for p in inputs:
        with open(p) as fh:
            data = fh.read()
        t0 = time.time()
        o = run(refcmd, data)
        dt = time.time() - t0
        if _unreliable(o):
            o = run(refcmd, data, timeout=BASE_TIMEOUT * 4)  # retry: assume transient contention
        if _unreliable(o):
            dropped.append(p)
            continue
        out[p] = o
        kept.append(p)
        max_t = max(max_t, dt)
    return out, kept, dropped, max_t


def killed_by(cmd, inputs, oracle, same, to=BASE_TIMEOUT):
    """Return the input path that kills `cmd`, or None if it survives (matches oracle everywhere).
    Every input here is reference-tractable (oracle_outputs guaranteed it), so a mutant that TIMES
    OUT or ERRORS on one has genuinely diverged (TLE / crash) and is KILLED. To make sure a one-off
    load spike can't fake that, an unreliable result is confirmed with a single larger-budget retry
    before it's trusted — if the retry then matches the oracle, it was just a blip and we move on."""
    for p in inputs:
        with open(p) as fh:
            data = fh.read()
        got = run(cmd, data, to)
        if _unreliable(got):
            got = run(cmd, data, to * 3)   # confirm real divergence vs. a transient load spike
            if _unreliable(got):
                return p                    # genuine TLE/crash on a tractable input -> killed
        if not same(got, oracle[p]):
            return p
    return None


def _fuzz_inputs(inputs, cap=60):
    """Generator-independent distinguishers: perturb integer tokens of the small existing inputs by
    +-1/+-2. Boundary mutants (< vs <=) die on exactly this kind of one-off nudge, so triage does not
    rely solely on the candidate's generator being lucky.

    CRITICAL: stay INSIDE the input grammar. Perturbing a COUNT field (e.g. the leading N) while
    leaving the payload rows intact makes a malformed input, on which the reference does something
    undefined and a harmless mutant (like an `i<n` -> `i<=n` loop bound) appears to 'differ' — a
    phantom gap that would poison the bank with an invalid edge test. So we only nudge tokens on
    PAYLOAD rows (lines with >=3 numeric tokens: arrays, edges, triples) and never a header/count
    line or the very first token of the input."""
    out = []
    for p in inputs[:6]:
        try:
            data = open(p).read()
        except Exception:
            continue
        if len(data.split()) > 60:
            continue
        lines = data.splitlines()
        for li, line in enumerate(lines):
            toks = line.split()
            nums = [j for j, t in enumerate(toks) if re.fullmatch(r"-?\d{1,7}", t)]
            if len(nums) < 3:
                continue  # header / count / small-scalar line: perturbing it desyncs the grammar
            for j in nums:
                if li == 0 and j == 0:
                    continue  # first token overall is almost always a size
                for delta in (1, -1, 2):
                    nl = toks[:]
                    nl[j] = str(int(toks[j]) + delta)
                    new_lines = lines[:]
                    new_lines[li] = " ".join(nl)
                    out.append("\n".join(new_lines) + "\n")
                    if len(out) >= cap:
                        return out
    return out


def find_distinguisher(mutant_cmd, refbin, gen, same, trials=80, inputs=(), to=BASE_TIMEOUT):
    """A mutant that passed the curated suite is EITHER equivalent (unkillable — not a weakness) OR a
    real wrong solution the suite simply misses. Decide by firing (a) random generator inputs and
    (b) +-1 fuzzes of the existing inputs at it: if one makes it disagree with the reference, THAT
    input is the exact missing edge case (a real gap); if none do, treat it as equivalent. A probe
    on which either side times out is skipped (we want a VALUE distinguisher to add as an edge test,
    not a timing-flaky one); the small `to` keeps a slow/looping mutant from stalling the probe."""
    # (a) generator-driven
    if os.path.exists(gen):
        sizes = [3, 6, 12, 25, 60, 150, 400]
        for k in range(trials):
            try:
                inp = subprocess.run([PY, gen, str(91237 + k), str(sizes[k % len(sizes)])],
                                     capture_output=True, text=True, timeout=10).stdout
            except Exception:
                continue
            if not inp.strip():
                continue
            mo, ro = run(mutant_cmd, inp, to), run([refbin], inp, to)
            if _unreliable(mo) or _unreliable(ro):
                continue  # can't trust a timeout as a disagreement -> not a real distinguisher
            if not same(mo, ro):
                return inp
    # (b) fuzz existing inputs (independent of the generator; nails boundary mutants)
    for inp in _fuzz_inputs(list(inputs)):
        mo, ro = run(mutant_cmd, inp, to), run([refbin], inp, to)
        if _unreliable(mo) or _unreliable(ro):
            continue
        if not same(mo, ro):
            return inp
    return None


def mutation_test_problem(pid, quick=False, verbose=True, fix=False):
    pdir = os.path.join(PROBLEMS, pid)
    ref = os.path.join(pdir, "reference.cpp")
    if not os.path.exists(ref):
        if verbose:
            print(f"  {pid}: SKIP (no reference.cpp; py-mutation not yet supported)")
        return None
    inputs = collect_inputs(pdir, quick)
    if not inputs:
        print(f"  {pid}: SKIP (no test inputs)")
        return None

    workdir = os.path.join("/tmp", "mut_" + pid.replace("/", "_"))
    os.makedirs(workdir, exist_ok=True)
    refbin = os.path.join(workdir, "ref")
    ok, err = compile_cpp(ref, refbin)
    if not ok:
        print(f"  {pid}: reference.cpp did not compile:\n{err}")
        return None
    oracle, inputs, dropped, max_ref_t = oracle_outputs([refbin], inputs)
    if dropped and verbose:
        print(f"  {pid}: NOTE: reference could not finish {len(dropped)} input(s) even after retry; "
              f"dropped from the mutation set (raise BASE_TIMEOUT if this is unexpected).")
    if not inputs:
        print(f"  {pid}: SKIP (no reliably-judgeable inputs)")
        return None
    # Per-mutant timeout scaled to the reference's OWN worst case: generous enough that a correct
    # mutant never false-times-out (>=6s, and >=15x the reference), but tight enough that a mutant
    # which infinite-loops is declared TLE-killed in seconds instead of stalling the whole run.
    mutant_to = max(6, min(BASE_TIMEOUT, int(15 * max_ref_t) + 1))
    try:
        import json
        compare = json.load(open(os.path.join(pdir, "problem.json"))).get("compare", "tokens")
    except Exception:
        compare = "tokens"
    same = make_same(compare)

    src = open(ref).read()
    muts = [(lbl, m) for lbl, m in cpp_mutants(src) + cpp_deletion_mutants(src) if m != src]
    whitelist = set()
    wf = os.path.join(pdir, ".mutants_ok")
    if os.path.exists(wf):
        whitelist = {l.strip() for l in open(wf) if l.strip()}

    mbase = os.path.join(workdir, "m")
    gen = os.path.join(pdir, "generator.py")

    def eval_mutant(item):
        idx, (label, mutated) = item
        cok, binp = compile_src(mutated, mbase, idx)
        if not cok:
            return ("compile_fail", label, None)
        if killed_by([binp], inputs, oracle, same, to=mutant_to) is not None:
            return ("killed", label, None)
        # Survived the curated suite: is it equivalent, or a real gap? Ask the generator.
        dist = find_distinguisher([binp], refbin, gen, same, inputs=inputs, to=mutant_to)
        if dist is None:
            return ("equivalent", label, None)   # unkillable by any input -> not a weakness
        return ("gap", label, dist)              # curated suite misses a killable wrong solution

    killed = gapped = compile_fail = equivalent = 0
    survivors = []  # (label, distinguishing_input)
    # Worker cap: each worker compiles bits/stdc++.h (hundreds of MB RAM). On a small WSL VM, stacking
    # too many concurrent compiles is what OOM-crashes the VM, so keep this conservative and let it be
    # overridden (OAJ_MUT_WORKERS=1 for a crash-safe serial run). NEVER run two of these concurrently.
    _mw = os.environ.get("OAJ_MUT_WORKERS")
    workers = max(1, int(_mw)) if _mw else max(1, min(4, (os.cpu_count() or 4)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for outcome, label, dist in ex.map(eval_mutant, enumerate(muts)):
            if outcome == "compile_fail":
                compile_fail += 1
            elif outcome == "killed":
                killed += 1
            elif outcome == "equivalent":
                equivalent += 1
            elif label in whitelist:
                continue
            else:
                gapped += 1
                survivors.append((label, dist))

    # planted wrongs (must all be killed)
    planted_fail = []
    wdir = os.path.join(pdir, "wrong")
    if os.path.isdir(wdir):
        for f in sorted(os.listdir(wdir)):
            fp = os.path.join(wdir, f)
            if f.endswith(".cpp"):
                wb = os.path.join(workdir, "w_" + f)
                cok, _ = compile_cpp(fp, wb)
                if not cok:
                    continue
                cmd = [wb]
            elif f.endswith(".py"):
                cmd = [PY, fp]
            else:
                continue
            if killed_by(cmd, inputs, oracle, same, to=mutant_to) is None:
                planted_fail.append(f)

    # --fix: persist each gap's distinguishing input as a curated edge test so the suite self-heals.
    if fix and survivors:
        edge = os.path.join(pdir, "tests", "edge")
        os.makedirs(edge, exist_ok=True)
        existing = [f for f in os.listdir(edge) if f.startswith("gap") and f.endswith(".in")]
        base = len(existing)
        added = 0
        for k, (label, dist) in enumerate(survivors):
            if not dist:
                continue
            fn = os.path.join(edge, f"gap{base + k:02d}.in")
            open(fn, "w").write(dist if dist.endswith("\n") else dist + "\n")
            added += 1
        if added:
            print(f"  {pid}: wrote {added} distinguishing edge test(s); "
                  f"run make_hidden.py then re-check.")

    # Score counts only KILLABLE mutants (killed + gaps); provable equivalents are excluded, so a
    # clean suite scores 100% honestly instead of being penalised for unkillable formatting mutants.
    total = killed + gapped
    score = (killed / total * 100) if total else 100.0
    status = "OK" if (gapped == 0 and not planted_fail) else "WEAK"
    if verbose or status == "WEAK":
        print(f"  {pid}: score {score:5.1f}%  killed {killed}/{total}  "
              f"(equiv {equivalent}, compile-fail {compile_fail})  {status}")
        for label, dist in survivors:
            print(f"      GAP: {label}")
            if dist:
                print(f"           distinguishing input (add as an edge test):\n"
                      f"           {dist.strip()[:300].replace(chr(10), chr(10)+'           ')}")
        for f in planted_fail:
            print(f"      PLANTED-WRONG SURVIVED: wrong/{f}")
    return {"pid": pid, "score": score, "gapped": gapped, "equivalent": equivalent,
            "survivors": survivors, "planted_fail": planted_fail}


def main():
    args = [a for a in sys.argv[1:]]
    quick = "--quick" in args
    do_all = "--all" in args
    fix = "--fix" in args
    args = [a for a in args if not a.startswith("--")]
    build_pch()
    if do_all:
        weak = []
        pids = sorted(d for d in os.listdir(PROBLEMS)
                      if os.path.exists(os.path.join(PROBLEMS, d, "reference.cpp")))
        for pid in pids:
            r = mutation_test_problem(pid, quick=quick, verbose=True)
            if r and (r["gapped"] or r["planted_fail"]):
                weak.append(r)
        print("\n=== WEAK SUITES ===" if weak else "\n=== ALL SUITES STRONG ===")
        for r in weak:
            print(f"  {r['pid']}: {len(r['survivors'])} survivors, "
                  f"{len(r['planted_fail'])} planted-wrong survived")
        sys.exit(1 if weak else 0)
    if not args:
        sys.exit(__doc__)
    r = mutation_test_problem(args[0], quick=quick, verbose=True, fix=fix)
    sys.exit(1 if (r and (r["gapped"] or r["planted_fail"])) else 0)


if __name__ == "__main__":
    main()
