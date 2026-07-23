"""Unified compile+run+judge on top of the language runners. Used by every endpoint."""
import shutil

from . import judge, run_cpp, run_py

RUNNERS = {"cpp": run_cpp, "py": run_py}


def compile_for(language: str, source: str):
    runner = RUNNERS.get(language)
    if runner is None:
        raise ValueError(f"unsupported language: {language}")
    return runner.compile_source(source)


def run_once(language: str, compiled, stdin_data: str, *, time_ms: int, memory_mb: int):
    """Run an already-compiled program once. Returns the raw RunResult."""
    return RUNNERS[language].run_binary(
        compiled.binary_path, stdin_data, time_ms=time_ms, memory_mb=memory_mb,
        cwd=compiled.workdir)


def judge_case(language: str, compiled, inp: str, expected: str, *,
               time_ms: int, memory_mb: int, compare: str):
    """Run one case and return (verdict, got_stdout, stderr, time_ms)."""
    res = run_once(language, compiled, inp, time_ms=time_ms, memory_mb=memory_mb)
    v = judge.verdict_for_run(res, memory_mb=memory_mb)
    if v is not None:
        return v, res.stdout, res.stderr, res.time_ms
    ok = judge.outputs_match(expected, res.stdout, compare)
    return ("AC" if ok else "WA"), res.stdout, res.stderr, res.time_ms


def cleanup(compiled):
    if compiled and compiled.workdir:
        shutil.rmtree(compiled.workdir, ignore_errors=True)
