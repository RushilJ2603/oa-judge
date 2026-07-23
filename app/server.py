"""OA Judge — Flask server. Serves the static UI and the JSON API defined in API.md."""
import os
import sys

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import execute, history, md, problems, stress  # noqa: E402

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
    solved = history.solved_ids()
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
        return jsonify({"verdict": "CE", "compile_output": compiled.compile_output,
                        "stdout": "", "stderr": "", "exit_code": None, "signal": None,
                        "time_ms": 0, "memory_kb": 0})
    res = execute.run_once(lang, compiled, stdin_data,
                           time_ms=p["meta"]["limits"]["time_ms"],
                           memory_mb=p["meta"]["limits"]["memory_mb"])
    execute.cleanup(compiled)
    from runner import judge
    v = judge.verdict_for_run(res, memory_mb=p["meta"]["limits"]["memory_mb"]) or "OK"
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

    compiled = execute.compile_for(lang, source)
    if not compiled.ok:
        execute.cleanup(compiled)
        history.record(p["meta"]["id"], lang, mode, "CE", 0, 0)
        return jsonify({"verdict": "CE", "compile_output": compiled.compile_output,
                        "passed": 0, "total": 0, "time_ms_max": 0, "tests": []})

    limits, compare = p["meta"]["limits"], p["meta"]["compare"]
    cases = ([("sample", t) for t in p["samples"]] +
             [("hidden", t) for t in p["hidden"]])
    results, passed, tmax, overall = [], 0, 0, "AC"
    for idx, (group, t) in enumerate(cases, start=1):
        v, got, stderr, tms = execute.judge_case(
            lang, compiled, t["input"], t["output"],
            time_ms=limits["time_ms"], memory_mb=limits["memory_mb"], compare=compare)
        tmax = max(tmax, tms)
        if v == "AC":
            passed += 1
        elif overall == "AC":
            overall = v                       # first failing verdict becomes the overall verdict
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
    history.record(p["meta"]["id"], lang, mode, overall, passed, total,
                   duration_s=body.get("duration_s"))
    return jsonify({"verdict": overall, "compile_output": "", "passed": passed,
                    "total": total, "time_ms_max": tmax, "tests": results})


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
    return jsonify({"attempts": history.attempts(),
                    "revisit": history.revisit_list(problems.list_ids())})


@app.route("/api/history/<pid>")
def api_history_one(pid):
    return jsonify({"attempts": history.attempts(pid),
                    "revisit": history.revisit_list(problems.list_ids())})


if __name__ == "__main__":
    port = int(os.environ.get("OAJ_PORT", "5000"))
    print(f"\n  OA Judge running →  http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
