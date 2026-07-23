"""Execution sandbox: run a subprocess under CPU/memory/output limits with a wall-clock timeout.

Not a security sandbox — this runs the user's own code on their own machine. The limits exist so a
runaway solution (infinite loop, unbounded allocation, print-flood) is reported as TLE/MLE instead of
freezing the app or filling the disk.
"""
import os
import resource
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


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
    """Execute argv under the configured backend. `local` runs a subprocess with rlimits on this
    host (correct when the code is your own); `docker` runs it inside an ephemeral, network-less
    container (use when hosting, so untrusted code cannot reach the host or the network)."""
    if config.EXEC_BACKEND == "docker":
        return _run_docker(argv, stdin_data, time_ms=time_ms, memory_mb=memory_mb,
                           cwd=cwd, output_cap_bytes=output_cap_bytes)
    return _run_local(argv, stdin_data, time_ms=time_ms, memory_mb=memory_mb,
                      cwd=cwd, output_cap_bytes=output_cap_bytes)


def _run_local(argv, stdin_data: str, *, time_ms: int, memory_mb: int,
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


def _run_docker(argv, stdin_data: str, *, time_ms: int, memory_mb: int,
                cwd: str | None = None, output_cap_bytes: int = 8 * 1024 * 1024) -> RunResult:
    """Run argv inside a throwaway, locked-down container. This is the isolation boundary for
    hosting untrusted code:

      --network none      no network at all (the #1 thing untrusted code must not have)
      --read-only         immutable root filesystem
      --tmpfs /work-rw    a small writable scratch area, capped, noexec
      --cap-drop ALL      no Linux capabilities
      --security-opt no-new-privileges
      --user 65534:65534  runs as 'nobody', never root
      --pids-limit        stops fork bombs
      --memory / --cpus   hard resource ceilings
      --rm                the container is deleted the moment it exits

    The compiled program / script lives in `cwd`, mounted read-only at /work. Wall-clock is
    enforced by coreutils `timeout` inside the container (exit 124), with an outer subprocess
    timeout as a backstop. Memory pressure surfaces as an OOM kill (exit 137)."""
    wall = time_ms / 1000.0 + 0.5
    workdir = cwd or "."

    # Re-root each argv path that points inside the workdir to its /work equivalent.
    mapped = []
    for a in argv:
        if a.startswith(workdir):
            mapped.append("/work" + a[len(workdir):])
        else:
            mapped.append(a)
    inner = "timeout -s KILL %d %s" % (int(wall) + 1, " ".join(shlex.quote(x) for x in mapped))

    docker_cmd = [
        "docker", "run", "--rm", "-i",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/work-rw:rw,noexec,nosuid,size=64m",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        "--pids-limit", str(config.DOCKER_PIDS),
        "--memory", f"{memory_mb}m", "--memory-swap", f"{memory_mb}m",
        "--cpus", str(config.DOCKER_CPUS),
        "-v", f"{os.path.abspath(workdir)}:/work:ro",
        "-w", "/work-rw",
        config.DOCKER_IMAGE,
        "/bin/sh", "-c", inner,
    ]

    start = time.monotonic()
    try:
        proc = subprocess.Popen(docker_cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as e:
        return RunResult("", f"failed to start container: {e}", 127, None, 0, 0, False, False)

    timed_out = False
    try:
        out, err = proc.communicate(input=stdin_data, timeout=wall + 5)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        out, err = proc.communicate()

    elapsed_ms = int((time.monotonic() - start) * 1000)
    rc = proc.returncode

    # coreutils `timeout -s KILL` exits 137 (128+SIGKILL) on timeout; docker also returns 137 on
    # an OOM kill. Distinguish by whether we were near the wall limit.
    if rc == 137 and elapsed_ms >= time_ms:
        timed_out = True
    oom = (rc == 137 and not timed_out) or ("bad_alloc" in (err or ""))

    sig_name = None
    if rc and rc > 128:
        try:
            sig_name = signal.Signals(rc - 128).name
        except ValueError:
            sig_name = f"SIG{rc - 128}"

    if out and len(out) > output_cap_bytes:
        out = out[:output_cap_bytes] + "\n...[output truncated]..."
    if err and len(err) > 64 * 1024:
        err = err[:64 * 1024] + "\n...[stderr truncated]..."

    return RunResult(out or "", err or "", rc if rc is not None else 0,
                     sig_name, elapsed_ms, 0, timed_out, oom)


def compile_argv(argv, *, cwd: str, timeout: int = 30):
    """Run a compiler command, on the host (local backend) or inside a network-less container
    with a writable /work (docker backend). Untrusted source must not be compiled on the host
    when hosting: a crafted #include can leak host files into the compiler diagnostics.

    Returns (returncode, combined_output)."""
    if config.EXEC_BACKEND != "docker":
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
            return p.returncode, (p.stderr or p.stdout or "")
        except subprocess.TimeoutExpired:
            return 124, "compilation timed out"

    mapped = ["/work" + a[len(cwd):] if a.startswith(cwd) else a for a in argv]
    docker_cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        "--pids-limit", str(config.DOCKER_PIDS),
        "--memory", "512m", "--memory-swap", "512m",
        "--cpus", str(config.DOCKER_CPUS),
        "-v", f"{os.path.abspath(cwd)}:/work:rw",   # compile needs to write the binary
        "-w", "/work",
        config.DOCKER_IMAGE,
        *mapped,
    ]
    try:
        p = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout + 10)
        return p.returncode, (p.stderr or p.stdout or "")
    except subprocess.TimeoutExpired:
        return 124, "compilation timed out"


def workspace() -> str:
    """A fresh temp dir for one compile/run cycle. Caller removes it."""
    return tempfile.mkdtemp(prefix="oaj_")
