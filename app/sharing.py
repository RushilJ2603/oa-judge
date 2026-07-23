"""Sharing: git operations over the oa-problems bank + authoring new problem packages.

The bank (config.PROBLEMS_DIR) is a git checkout of oa-problems. These helpers let the app
pull everyone's latest problems, scaffold a new package, verify it, and publish it on a branch —
all without the user touching a terminal.

Every git call is scoped to the bank directory with an explicit timeout, so a network hang or a
non-repo directory returns a clean error instead of freezing a request.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402

BANK = config.PROBLEMS_DIR
ROOT = os.path.dirname(HERE)                     # oa-judge/


# ------------------------------------------------------------------ git plumbing
def _git(*args, timeout=60):
    """Run a git command inside the bank. Returns (ok, stdout, stderr)."""
    try:
        r = subprocess.run(["git", "-C", BANK, *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", f"git {args[0]} timed out"
    except FileNotFoundError:
        return False, "", "git is not installed"


def is_repo() -> bool:
    ok, out, _ = _git("rev-parse", "--is-inside-work-tree")
    return ok and out == "true"


def status() -> dict:
    """Branch, whether a remote exists, and how dirty/ahead/behind the bank is."""
    if not is_repo():
        return {"repo": False, "reason": "problems/ is not a git checkout"}
    _, branch, _ = _git("rev-parse", "--abbrev-ref", "HEAD")
    ok_remote, remote, _ = _git("remote", "get-url", "origin")
    _, dirty, _ = _git("status", "--porcelain")
    _, count, _ = _git("rev-list", "--count", "HEAD")
    return {
        "repo": True,
        "branch": branch,
        "has_remote": ok_remote,
        "remote": remote if ok_remote else None,
        "dirty": bool(dirty.strip()),
        "commits": int(count) if count.isdigit() else None,
    }


def sync() -> dict:
    """Fetch + fast-forward the bank from origin, then report what changed.

    Uses --ff-only so a Sync can never create a merge commit or silently clobber local edits;
    if history diverged, we say so and leave it to the user rather than guessing."""
    if not is_repo():
        return {"ok": False, "error": "problems/ is not a git checkout — nothing to sync"}
    ok_remote, _, _ = _git("remote", "get-url", "origin")
    if not ok_remote:
        return {"ok": False, "error": "no 'origin' remote set on the problems bank yet"}

    _, before, _ = _git("rev-parse", "HEAD")
    ok, _, err = _git("fetch", "origin", timeout=120)
    if not ok:
        return {"ok": False, "error": f"fetch failed: {err}"}
    ok, out, err = _git("merge", "--ff-only", "@{u}", timeout=60)
    if not ok:
        # Local commits that aren't upstream, or a dirty tree, block a fast-forward.
        return {"ok": False, "error": "cannot fast-forward (local changes or diverged history). "
                                      "Publish or stash your local problems first.",
                "detail": err}
    _, after, _ = _git("rev-parse", "HEAD")

    added = []
    if before != after:
        _, names, _ = _git("diff", "--name-only", f"{before}..{after}")
        # Surface which problems appeared/changed (top-level dir under the bank).
        added = sorted({n.split("/", 1)[0] for n in names.splitlines()
                        if "/" in n and not n.startswith(".")})
    return {"ok": True, "changed": before != after, "new_or_changed": added}


# ------------------------------------------------------------------ authoring
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_id(pid: str) -> str | None:
    if not pid or not ID_RE.match(pid):
        return "id must be lowercase words separated by hyphens (e.g. company-q1-short-name)"
    if os.path.exists(os.path.join(BANK, pid)):
        return f"a problem named '{pid}' already exists"
    return None


def scaffold(spec: dict) -> dict:
    """Write a new problem package to disk from an authoring spec. Does NOT publish; the caller
    verifies first. Returns the created directory or an error."""
    pid = (spec.get("id") or "").strip()
    err = validate_id(pid)
    if err:
        return {"ok": False, "error": err}

    lang = spec.get("language", "cpp")
    if lang not in ("cpp", "py"):
        return {"ok": False, "error": "language must be cpp or py"}
    reference = spec.get("reference", "")
    if not reference.strip():
        return {"ok": False, "error": "a reference solution is required (it defines correct output)"}

    samples = spec.get("samples") or []
    if not samples:
        return {"ok": False, "error": "at least one sample (input + expected output) is required"}

    pdir = os.path.join(BANK, pid)
    os.makedirs(os.path.join(pdir, "tests", "sample"), exist_ok=True)
    os.makedirs(os.path.join(pdir, "tests", "edge"), exist_ok=True)
    os.makedirs(os.path.join(pdir, "tests", "hidden"), exist_ok=True)

    meta = {
        "id": pid,
        "title": spec.get("title", pid),
        "company": spec.get("company", ""),
        "difficulty": spec.get("difficulty", "Medium"),
        "tags": spec.get("tags", []),
        "languages": [lang],
        "runnable": True,
        "links": spec.get("links", {}),
        "limits": {"time_ms": int(spec.get("time_ms", 2000)),
                   "memory_mb": int(spec.get("memory_mb", 256))},
        "compare": spec.get("compare", "token"),
        "author": spec.get("author") or config.AUTHOR,
    }
    _w(os.path.join(pdir, "problem.json"), json.dumps(meta, indent=2) + "\n")
    _w(os.path.join(pdir, "statement.md"), spec.get("statement", "") or f"# {meta['title']}\n")
    if spec.get("editorial"):
        _w(os.path.join(pdir, "editorial.md"), spec["editorial"])
    ref_name = "reference.cpp" if lang == "cpp" else "reference.py"
    stub_name = "stub.cpp" if lang == "cpp" else "stub.py"
    _w(os.path.join(pdir, ref_name), reference)
    _w(os.path.join(pdir, stub_name), spec.get("stub", "") or _default_stub(lang))
    if spec.get("generator"):
        _w(os.path.join(pdir, "generator.py"), spec["generator"])

    for i, s in enumerate(samples, start=1):
        _w(os.path.join(pdir, "tests", "sample", f"{i:02d}.in"), _nl(s.get("input", "")))
        _w(os.path.join(pdir, "tests", "sample", f"{i:02d}.out"), _nl(s.get("output", "")))
    for i, e in enumerate(spec.get("edge") or [], start=1):
        _w(os.path.join(pdir, "tests", "edge", f"{i:02d}.in"), _nl(e if isinstance(e, str) else e.get("input", "")))

    return {"ok": True, "dir": pdir, "id": pid}


def verify_one(pid: str) -> dict:
    """Run the project's verifier against just this problem. Reference must reproduce its
    samples and the package must be wired correctly, or publishing is refused."""
    verifier = os.path.join(ROOT, "verify_all.py")
    if not os.path.exists(verifier):
        return {"ok": False, "error": "verify_all.py not found"}
    env = dict(os.environ, OAJ_PROBLEMS_DIR=BANK)
    try:
        r = subprocess.run([sys.executable, verifier, pid],
                           capture_output=True, text=True, timeout=300, env=env, cwd=ROOT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "verification timed out"}
    return {"ok": r.returncode == 0, "output": (r.stdout + r.stderr).strip()}


def make_hidden(pid: str) -> dict:
    """Generate the hidden test suite (curated edge + random) for a freshly authored problem."""
    script = os.path.join(ROOT, "make_hidden.py")
    if not os.path.exists(script):
        return {"ok": True, "skipped": "make_hidden.py not found"}
    env = dict(os.environ, OAJ_PROBLEMS_DIR=BANK)
    try:
        r = subprocess.run([sys.executable, script, pid],
                           capture_output=True, text=True, timeout=300, env=env, cwd=ROOT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "make_hidden timed out"}
    return {"ok": r.returncode == 0, "output": (r.stdout + r.stderr).strip()}


def publish(pid: str, message: str = "") -> dict:
    """Commit the new/changed problem on its own branch and push it. Returns the branch and,
    if a GitHub remote is set, a ready-to-open PR URL. Never pushes straight to main."""
    if not is_repo():
        return {"ok": False, "error": "problems/ is not a git checkout"}
    branch = f"add-{pid}"
    _git("add", os.path.join(BANK, pid))
    # Stage only this problem's files, so an unrelated local edit isn't swept in.
    ok, _, err = _git("commit", "-m", message or f"Add problem: {pid}")
    if not ok and "nothing to commit" not in err.lower():
        return {"ok": False, "error": f"commit failed: {err}"}

    ok_remote, remote, _ = _git("remote", "get-url", "origin")
    if not ok_remote:
        return {"ok": True, "committed": True, "pushed": False,
                "note": "committed locally; no 'origin' remote yet, so nothing was pushed"}

    _git("branch", "-M", branch)
    ok, _, err = _git("push", "-u", "origin", branch, timeout=120)
    if not ok:
        return {"ok": False, "error": f"push failed: {err}"}
    return {"ok": True, "pushed": True, "branch": branch, "pr_url": _pr_url(remote, branch)}


# ------------------------------------------------------------------ helpers
def _w(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _nl(s: str) -> str:
    """Ensure a trailing newline; judges compare token streams but files should be POSIX-clean."""
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    return s if s.endswith("\n") else s + "\n"


def _default_stub(lang: str) -> str:
    if lang == "cpp":
        return ("#include <bits/stdc++.h>\nusing namespace std;\n\n"
                "int main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n\n"
                "    // your code here\n\n    return 0;\n}\n")
    return "import sys\ninput = sys.stdin.readline\n\ndef main():\n    # your code here\n    pass\n\nmain()\n"


def _pr_url(remote: str, branch: str) -> str | None:
    """Turn a GitHub remote (ssh or https) into a compare/PR URL."""
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", remote or "")
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    return f"https://github.com/{owner}/{repo}/pull/new/{branch}"
