"""Output comparison and verdict mapping."""
from .sandbox import RunResult


def normalize_tokens(s: str) -> list[str]:
    """Whitespace-insensitive: split on any run of whitespace, drop leading/trailing.

    This is the standard competitive/OA comparison — it ignores trailing newlines and spacing
    differences, which are almost never what a problem intends to distinguish.
    """
    return s.split()


def normalize_exact(s: str) -> str:
    """Exact match modulo a single trailing newline and trailing spaces per line."""
    lines = s.replace("\r\n", "\n").split("\n")
    lines = [ln.rstrip() for ln in lines]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def outputs_match(expected: str, got: str, compare: str) -> bool:
    if compare == "exact":
        return normalize_exact(expected) == normalize_exact(got)
    return normalize_tokens(expected) == normalize_tokens(got)


def verdict_for_run(res: RunResult, *, memory_mb: int) -> str | None:
    """Map an execution result to a failing verdict, or None if the program ran cleanly.

    None means "ran to completion, exit 0" — the caller then compares output for AC/WA.
    """
    if res.timed_out:
        return "TLE"
    if res.oom:
        return "MLE"
    if res.signal_name is not None:
        # A memory-limit hit often manifests as a signal; distinguish the common OOM case.
        if res.signal_name in ("SIGABRT",) and "bad_alloc" in (res.stderr or ""):
            return "MLE"
        return "RE"
    if res.exit_code != 0:
        return "RE"
    return None
