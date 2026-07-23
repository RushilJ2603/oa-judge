"""Execution sandbox: run a subprocess under CPU/memory/output limits with a wall-clock timeout.

Not a security sandbox — this runs the user's own code on their own machine. The limits exist so a
runaway solution (infinite loop, unbounded allocation, print-flood) is reported as TLE/MLE instead of
freezing the app or filling the disk.
"""
import os
import resource
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int          # process exit code (0 on success)
    signal_name: str | None # e.g. "SIGSEGV" if killed by a signal, else None
    time_ms: int
    memory_kb: int
    timed_out: bool
    oom: bool               # heuristic: killed while near the memory cap / bad_alloc seen


def _preexec(cpu_s: int, mem_bytes: int, fsize_bytes: int):
    """Runs in the child after fork, before exec. Installs the resource limits."""
    def apply():
        # New process group so we can kill the whole tree on timeout.
        os.setsid()
        # Hard CPU ceiling (SIGXCPU then SIGKILL) — backstop for the wall-clock timeout.
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        # Address-space ceiling — an over-allocating program hits bad_alloc / gets killed.
        if mem_bytes:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        # Cap the size of any single file the program writes (stops disk-fill via stdout redirect).
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))
        # No core dumps.
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def run(argv, stdin_data: str, *, time_ms: int, memory_mb: int,
        cwd: str | None = None, output_cap_bytes: int = 8 * 1024 * 1024) -> RunResult:
    """Execute argv, feed stdin_data, enforce limits. Never raises for program-level failure."""
    wall_timeout = time_ms / 1000.0 + 0.5          # wall grace over the CPU limit
    cpu_s = max(1, int(time_ms / 1000.0) + 1)
    mem_bytes = memory_mb * 1024 * 1024
    fsize = output_cap_bytes

    start = time.monotonic()
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        proc = subprocess.Popen(
            argv, cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=_preexec(cpu_s, mem_bytes, fsize),
            text=True,
        )
    except OSError as e:
        return RunResult("", f"failed to start: {e}", 127, None, 0, 0, False, False)

    timed_out = False
    try:
        out, err = proc.communicate(input=stdin_data, timeout=wall_timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        # Kill the whole process group; the child may have spawned helpers.
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = proc.communicate()
    except (MemoryError, ValueError):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = "", ""

    elapsed_ms = int((time.monotonic() - start) * 1000)
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    mem_kb = int(usage_after.ru_maxrss - usage_before.ru_maxrss)
    if mem_kb < 0:
        mem_kb = int(usage_after.ru_maxrss)

    rc = proc.returncode
    sig_name = None
    if rc is not None and rc < 0:
        try:
            sig_name = signal.Signals(-rc).name
        except ValueError:
            sig_name = f"SIG{-rc}"

    # OOM heuristic: RLIMIT_AS violations usually surface as SIGSEGV/SIGABRT or a bad_alloc message.
    oom = (mem_kb >= mem_bytes // 1024 * 0.98) or ("bad_alloc" in (err or "")) \
        or (sig_name in ("SIGABRT",) and "bad_alloc" in (err or ""))

    # Truncate pathological output so the response stays sane.
    if out and len(out) > output_cap_bytes:
        out = out[:output_cap_bytes] + "\n...[output truncated]..."
    if err and len(err) > 64 * 1024:
        err = err[:64 * 1024] + "\n...[stderr truncated]..."

    return RunResult(out or "", err or "", rc if rc is not None else 0,
                     sig_name, elapsed_ms, mem_kb, timed_out, oom)


def workspace() -> str:
    """A fresh temp dir for one compile/run cycle. Caller removes it."""
    return tempfile.mkdtemp(prefix="oaj_")
