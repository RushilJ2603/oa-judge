"""OA Judge — Flask server. Serves the static UI and the JSON API defined in API.md."""
import os
import sys

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402
import store  # noqa: E402  (v2 SQLite persistence; replaces runner.history)
from runner import execute, md, problems, stress  # noqa: E402

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app = Flask(__name__, static_folder=None)


# ----------------------------------------------------------------- static UI
@app.after_request
def _no_cache(resp):
    # Local dev tool: never let the browser serve stale index.html/app.js/style.css.
    # (A cached editor is exactly why a CSS fix can look like "still broken" after reload.)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


# ----------------------------------------------------------------- problem list / detail
@app.route("/api/problems")
def api_problems():
    solved = store.solved_ids()
    items = []
    for pid in problems.list_ids():
        s = problems.summary(pid)
        if s is None:
            continue
        s["solved"] = pid in solved
        items.append(s)
    return jsonify({"problems": items})


@app.route("/api/problem/<pid>")
def api_problem(pid):
    p = problems.load(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    m = p["meta"]
    return jsonify({
        "id": m["id"], "title": m.get("title", m["id"]),
        "company": m.get("company", ""), "difficulty": m.get("difficulty", ""),
        "tags": m.get("tags", []),
        "statement_html": md.render(p["statement_md"]),
        "editorial_html": md.render(p["editorial_md"]) if p["editorial_md"] else "",
        "languages": m["languages"], "runnable": m["runnable"], "links": m["links"],
        "limits": m["limits"], "stubs": p["stubs"],
        "samples": [{"index": t["index"], "input": t["input"], "output": t["output"]}
                    for t in p["samples"]],
        "hidden_count": len(p["hidden"]),
    })


# ----------------------------------------------------------------- run (custom input)
@app.route("/api/run", methods=["POST"])
def api_run():
    body = request.get_json(force=True)
    p = problems.load(body["problem_id"])
    if p is None:
        return jsonify({"error": "not found"}), 404
    lang, source = body["language"], body["source"]
    stdin_data = body.get("stdin", "")
    if lang not in p["meta"]["languages"]:
        return jsonify({"error": f"language {lang} not enabled for this problem"}), 400

    compiled = execute.compile_for(lang, source)
    if not compiled.ok:
        execute.cleanup(compiled)
        store.record_run(p["meta"]["id"], lang, source, stdin_data, "",
                         compiled.compile_output, verdict="CE")
        return jsonify({"verdict": "CE", "compile_output": compiled.compile_output,
                        "stdout": "", "stderr": "", "exit_code": None, "signal": None,
                        "time_ms": 0, "memory_kb": 0})
    res = execute.run_once(lang, compiled, stdin_data,
                           time_ms=p["meta"]["limits"]["time_ms"],
                           memory_mb=p["meta"]["limits"]["memory_mb"])
    execute.cleanup(compiled)
    from runner import judge
    v = judge.verdict_for_run(res, memory_mb=p["meta"]["limits"]["memory_mb"]) or "OK"
    # v1 did not log runs at all — you could never look back at what you tried.
    store.record_run(p["meta"]["id"], lang, source, stdin_data, res.stdout, res.stderr,
                     exit_code=res.exit_code, signal=res.signal_name,
                     runtime_ms=res.time_ms, verdict=v)
    return jsonify({
        "verdict": v, "compile_output": "", "stdout": res.stdout, "stderr": res.stderr,
        "exit_code": res.exit_code, "signal": res.signal_name,
        "time_ms": res.time_ms, "memory_kb": res.memory_kb,
    })


# ----------------------------------------------------------------- submit (judge)
@app.route("/api/submit", methods=["POST"])
def api_submit():
    body = request.get_json(force=True)
    p = problems.load(body["problem_id"])
    if p is None:
        return jsonify({"error": "not found"}), 404
    lang, source = body["language"], body["source"]
    mode = body.get("mode", "lc")
    if lang not in p["meta"]["languages"]:
        return jsonify({"error": f"language {lang} not enabled for this problem"}), 400

    # Snapshot the exact code being judged before anything can overwrite it.
    store.snapshot_draft(p["meta"]["id"], lang, source, reason="pre-submit")

    compiled = execute.compile_for(lang, source)
    if not compiled.ok:
        execute.cleanup(compiled)
        attempt_id = store.record_attempt(
            p["meta"]["id"], lang, mode, "CE", 0, 0,
            source_code=source,
            compile_output=compiled.compile_output,
            duration_s=body.get("duration_s"))
        return jsonify({"verdict": "CE", "compile_output": compiled.compile_output,
                        "passed": 0, "total": 0, "time_ms_max": 0, "tests": [],
                        "attempt_id": attempt_id})

    limits, compare = p["meta"]["limits"], p["meta"]["compare"]
    cases = ([("sample", t) for t in p["samples"]] +
             [("hidden", t) for t in p["hidden"]])
    results, passed, tmax, overall = [], 0, 0, "AC"
    first_fail_idx = None
    fail_got = fail_stderr = None
    for idx, (group, t) in enumerate(cases, start=1):
        v, got, stderr, tms = execute.judge_case(
            lang, compiled, t["input"], t["output"],
            time_ms=limits["time_ms"], memory_mb=limits["memory_mb"], compare=compare)
        tmax = max(tmax, tms)
        if v == "AC":
            passed += 1
        elif overall == "AC":
            overall = v                       # first failing verdict becomes the overall verdict
            first_fail_idx = idx
            fail_got, fail_stderr = got, stderr   # kept for the attempt record, not the response
        visible = (group == "sample") or (mode == "lc")
        row = {"index": idx, "group": group, "verdict": v, "time_ms": tms, "visible": visible}
        if visible:
            row.update({"input": t["input"], "expected": t["output"],
                        "got": got, "stderr": stderr})
        results.append(row)
        # OA mode stops the solver from learning more than "test k failed": keep judging so the
        # index is right, but never leak I/O. (We still run every test for an honest pass count.)

    execute.cleanup(compiled)
    total = len(cases)
    if total == 0:
        overall = "AC"
    attempt_id = store.record_attempt(
        p["meta"]["id"], lang, mode, overall, passed, total,
        source_code=source, duration_s=body.get("duration_s"), runtime_ms=tmax,
        first_fail_idx=first_fail_idx,
        stdout_snippet=fail_got, stderr_snippet=fail_stderr)

    # Close an OA session if the frontend opened one, so time-per-problem is real data
    # rather than the NULL every v1 row carried.
    sid = body.get("oa_session_id")
    if sid:
        store.end_oa_session(int(sid), duration_s=body.get("duration_s"), result=overall)

    return jsonify({"verdict": overall, "compile_output": "", "passed": passed,
                    "total": total, "time_ms_max": tmax, "tests": results,
                    "attempt_id": attempt_id})


# ----------------------------------------------------------------- stress
@app.route("/api/stress", methods=["POST"])
def api_stress():
    body = request.get_json(force=True)
    p = problems.load(body["problem_id"])
    if p is None:
        return jsonify({"error": "not found"}), 404
    lang, source = body["language"], body["source"]
    if lang not in p["meta"]["languages"]:
        return jsonify({"error": f"language {lang} not enabled"}), 400
    iters = int(body.get("iterations", 300))
    return jsonify(stress.run(p, lang, source, iterations=iters))


# ----------------------------------------------------------------- history
@app.route("/api/history")
def api_history():
    return jsonify({"attempts": store.attempts(),
                    "revisit": store.revisit_list(problems.list_ids())})


@app.route("/api/history/<pid>")
def api_history_one(pid):
    return jsonify({"attempts": store.attempts(pid),
                    "revisit": store.revisit_list(problems.list_ids())})


# ----------------------------------------------------------------- attempts (with code)
@app.route("/api/attempt/<int:attempt_id>")
def api_attempt(attempt_id):
    """Full attempt including the source that was judged — the code viewer and diff use this."""
    a = store.attempt(attempt_id)
    if a is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(a)


# ----------------------------------------------------------------- drafts (autosave)
@app.route("/api/draft/<pid>/<lang>", methods=["GET"])
def api_get_draft(pid, lang):
    return jsonify(store.get_draft(pid, lang) or {})


@app.route("/api/draft/<pid>/<lang>", methods=["PUT"])
def api_put_draft(pid, lang):
    """Debounced autosave target. Replaces browser localStorage, which was per-origin
    (so the 5000 -> 5137 port move stranded it) and kept no history."""
    body = request.get_json(force=True)
    store.save_draft(pid, lang, body.get("source", ""), body.get("cursor_pos"))
    return jsonify({"ok": True})


@app.route("/api/drafts")
def api_all_drafts():
    return jsonify({"drafts": store.all_drafts()})


# ----------------------------------------------------------------- snapshots (time travel)
@app.route("/api/snapshots/<pid>")
def api_snapshots(pid):
    return jsonify({"snapshots": store.snapshots(pid, request.args.get("lang"))})


@app.route("/api/snapshot/<int:snapshot_id>")
def api_snapshot(snapshot_id):
    s = store.snapshot(snapshot_id)
    if s is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(s)


@app.route("/api/snapshot", methods=["POST"])
def api_make_snapshot():
    body = request.get_json(force=True)
    sid = store.snapshot_draft(body["problem_id"], body["language"],
                               body.get("source", ""), body.get("reason", "periodic"))
    return jsonify({"ok": True, "snapshot_id": sid})   # sid is null when unchanged


# ----------------------------------------------------------------- runs
@app.route("/api/runs/<pid>")
def api_runs(pid):
    return jsonify({"runs": store.runs(pid)})


# ----------------------------------------------------------------- OA sessions
@app.route("/api/oa-session", methods=["POST"])
def api_start_oa_session():
    body = request.get_json(force=True)
    return jsonify({"session_id": store.start_oa_session(body["problem_id"])})


@app.route("/api/oa-session/<int:session_id>", methods=["DELETE"])
def api_abandon_oa_session(session_id):
    store.end_oa_session(session_id, abandoned=True)
    return jsonify({"ok": True})


# ----------------------------------------------------------------- notes / flags
@app.route("/api/note/<pid>", methods=["GET", "PUT"])
def api_note(pid):
    if request.method == "PUT":
        store.save_note(pid, request.get_json(force=True).get("body", ""))
        return jsonify({"ok": True})
    return jsonify({"body": store.get_note(pid)})


@app.route("/api/flags/<pid>", methods=["GET", "PUT"])
def api_flags(pid):
    if request.method == "PUT":
        b = request.get_json(force=True)
        store.save_flags(pid, b.get("starred"), b.get("revisit"), b.get("confidence"))
        return jsonify({"ok": True})
    return jsonify(store.get_flags(pid))


# ----------------------------------------------------------------- stats / health
@app.route("/api/stats")
def api_stats():
    return jsonify(store.stats())


@app.route("/api/export")
def api_export():
    """Everything you've produced as a downloadable zip: the raw DB plus a readable tree of
    your submitted code and notes as plain files. Your data is never locked inside this app."""
    import io
    import zipfile
    from datetime import datetime

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # The database itself, so an export is a complete backup.
        if os.path.exists(db.DB_PATH):
            z.write(db.DB_PATH, "judge.db")
        # Human-readable copies: latest attempt code + notes per problem.
        ext = {"cpp": "cpp", "py": "py"}
        for a in store.attempts(limit=100000):
            if not a.get("has_code"):
                continue
            full = store.attempt(a["id"])
            if not full or not full.get("source_code"):
                continue
            e = ext.get(full["language"], "txt")
            path = f"code/{a['problem_id']}/attempt-{a['id']}-{full['verdict']}.{e}"
            z.writestr(path, full["source_code"])
        for pid in problems.list_ids():
            note = store.get_note(pid)
            if note.strip():
                z.writestr(f"notes/{pid}.md", note)
    buf.seek(0)
    from flask import send_file
    stamp = datetime.now().strftime("%Y%m%d")
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"oa-judge-export-{stamp}.zip")


@app.route("/api/health")
def api_health():
    """Used by the launcher to detect an already-running instance instead of colliding."""
    import shutil
    return jsonify({"ok": True, "version": 2,
                    "db": db.DB_PATH,
                    "gpp": bool(shutil.which("g++")),
                    "problems": len(problems.list_ids())})


def _already_running(port: int) -> bool:
    """True if an OA Judge instance is already answering on this port. Double-clicking the
    launcher twice otherwise crashes on 'address already in use' with a confusing traceback."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1.5) as r:
            import json as _json
            return _json.load(r).get("ok") is True
    except Exception:
        return False


def _serve(port: int) -> None:
    """Prefer waitress (a real WSGI server) when it is installed; otherwise fall back to the
    Flask dev server. Both are fine for single-user local use — waitress just handles
    concurrent requests more gracefully (e.g. a long stress run while you browse)."""
    try:
        from waitress import serve as waitress_serve
        print("  (serving via waitress)")
        waitress_serve(app, host="127.0.0.1", port=port, threads=8, _quiet=True)
    except ImportError:
        # Not installed, and we deliberately do not force it into an externally-managed
        # Python. `pip install waitress` upgrades this automatically next launch.
        app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    port = int(os.environ.get("OAJ_PORT", "5137"))
    if _already_running(port):
        print(f"\n  OA Judge is already running →  http://127.0.0.1:{port}")
        print("  (Opening a second copy is unnecessary; using the existing one.)\n")
        sys.exit(0)
    # Warm the DB / apply migrations before accepting requests, so the first click is instant
    # and any migration error surfaces here rather than mid-request.
    db.connect()
    print(f"\n  OA Judge running →  http://127.0.0.1:{port}\n")
    _serve(port)
