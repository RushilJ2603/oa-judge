"""Python runner: a syntax pre-check (so bad syntax reads as CE, like C++), then execute."""
import os
import subprocess
import sys

from . import sandbox

PYTHON = sys.executable or "python3"


class Compiled:
    """Mirror of run_cpp.Compiled so the server can treat both languages uniformly.

    For Python there is no binary; `binary_path` is the source file to run with the interpreter.
    """
    def __init__(self, ok, source_path, workdir, compile_output):
        self.ok = ok
        self.binary_path = source_path
        self.workdir = workdir
        self.compile_output = compile_output


def compile_source(source: str, *, compile_timeout: int = 10) -> Compiled:
    wd = sandbox.workspace()
    src = os.path.join(wd, "sol.py")
    with open(src, "w") as f:
        f.write(source)
    # py_compile gives a real SyntaxError location, surfaced to the user as compile output.
    proc = subprocess.run([PYTHON, "-m", "py_compile", src],
                          capture_output=True, text=True, timeout=compile_timeout)
    if proc.returncode != 0:
        return Compiled(False, None, wd, proc.stderr or "syntax error")
    return Compiled(True, src, wd, "")


def run_binary(source_path: str, stdin_data: str, *, time_ms: int, memory_mb: int,
               cwd: str | None = None) -> sandbox.RunResult:
    # Python needs more headroom than compiled code; scale the limits so a correct
    # solution is not falsely TLE'd/MLE'd by interpreter overhead.
    return sandbox.run([PYTHON, source_path], stdin_data,
                       time_ms=time_ms * 3, memory_mb=memory_mb + 128, cwd=cwd)
