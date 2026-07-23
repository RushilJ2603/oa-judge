"""C++ runner: compile with g++, then execute the binary under the sandbox."""
import os
import subprocess

from . import sandbox

GXX = "g++"
STD = "-std=c++17"


class Compiled:
    def __init__(self, ok, binary_path, workdir, compile_output):
        self.ok = ok
        self.binary_path = binary_path
        self.workdir = workdir
        self.compile_output = compile_output


def compile_source(source: str, *, compile_timeout: int = 20) -> Compiled:
    """Compile source into a binary in a fresh workspace. Returns Compiled(ok, ...)."""
    wd = sandbox.workspace()
    src = os.path.join(wd, "sol.cpp")
    binp = os.path.join(wd, "sol")
    with open(src, "w") as f:
        f.write(source)
    try:
        proc = subprocess.run(
            [GXX, STD, "-O2", "-pipe", "-w", "-o", binp, src],
            capture_output=True, text=True, timeout=compile_timeout,
        )
    except subprocess.TimeoutExpired:
        return Compiled(False, None, wd, "compilation timed out")
    if proc.returncode != 0:
        return Compiled(False, None, wd, proc.stderr or proc.stdout or "compilation failed")
    return Compiled(True, binp, wd, "")


def run_binary(binary_path: str, stdin_data: str, *, time_ms: int, memory_mb: int,
               cwd: str | None = None) -> sandbox.RunResult:
    return sandbox.run([binary_path], stdin_data, time_ms=time_ms, memory_mb=memory_mb, cwd=cwd)
